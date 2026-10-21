"""The sound engine: playback, live playing, metronome and recording.

The engine produces audio one block at a time through `process()`. The same
code runs in real time (called by the audio device) and offline (for
exporting a WAV file), so what you export is exactly what you hear.

Threads: the user interface never touches the synthesizer directly. It sends
commands through a queue (play, stop, note on, and so on), and the audio
thread applies them at the start of the next block. Messages back to the user
interface (a finished recording, "stopped at the end of the song") go
through a second queue.

The arpeggiator runs here too, so its notes are sample-accurate: while the
song plays they land exactly on the beat grid (and are recorded), and while
stopped they follow the song's tempo on their own clock.

Audio tracks: recordings are mixed in sample-accurately as well. The microphone
arrives through a third queue (from the input stream's thread); each piece is
stamped with when it was captured, so a take lands where the performer heard
the beat, whatever the sound card delays are.
"""

import logging
import math
import queue
import random
import time
from collections import namedtuple

import numpy as np

from . import arpeggiator, audiotracks, effects, latency
from . import automation as automation_module
from .song import AUDIO_RATE, Note
from .startfade import StartFade
from .timeline import PPQ

log = logging.getLogger("musicianforge.engine")

ChannelSetup = namedtuple("ChannelSetup", "bank program drum volume_cc pan_cc")
# how one track is mixed: its kind ("instrument" or "audio"), volume (0 to 100), pan (-100 to 100),
# effects (the list from the project) and its id
TrackMix = namedtuple("TrackMix", "kind volume pan effects track_id")

MIN_RECORDED_LENGTH = 60          # ticks: very short taps still make a sound
RECORD_GRACE_TICKS = PPQ // 4     # a note up to a sixteenth early is pulled onto the start
END_OF_SONG_SECONDS = 2.0         # keep playing this long after the last note ends


def volume_to_cc(percent):
    return max(0, min(127, int(round(percent * 127 / 100.0))))


def pan_to_cc(pan):
    return max(0, min(127, int(round(64 + pan * 63 / 100.0))))


def track_gains(kind, volume, pan):
    """(left, right) gains for a track's volume and pan.

    Volume follows the same curve as before (FluidSynth's own volume control): (volume / 100)
    squared. Instrument tracks pan the way FluidSynth did (constant power, full level in the
    middle); audio tracks use a balance control (the far side fades out)."""
    level = (max(0.0, min(100.0, float(volume))) / 100.0) ** 2
    pan = max(-100.0, min(100.0, float(pan))) / 100.0
    if pan == 0.0:
        return level, level
    if kind == "audio":
        return level * min(1.0, 1.0 - pan), level * min(1.0, 1.0 + pan)
    angle = (pan + 1.0) * math.pi / 4.0
    return level * math.sqrt(2.0) * math.cos(angle), level * math.sqrt(2.0) * math.sin(angle)


class PlaybackData:
    """An unchangeable snapshot of what the song should play.

    Built on the user-interface thread whenever the song changes, then handed
    to the engine, which swaps it in between two audio blocks.
    """

    def __init__(self, song=None, sample_rate=48000, audio_loader=None, take_loader=None, effects_override=None,
                 notes_by_track=None):
        """audio_loader(file) returns a recording as float32 (frames, channels), or None if missing.
        take_loader(track, region), if given, is used instead (it can hand back a pitch-corrected copy).
        effects_override: {track id: effect list} to hear instead of the saved ones (while an
        effect's settings are being changed).
        notes_by_track: {track id: notes} that a track really plays (looped regions repeated, rhythm
        players performed, muted regions left out; see arrangement.py). Without it, a track plays its
        own notes."""
        from .timeline import Timeline

        self.sample_rate = sample_rate
        self.timeline = song.timeline.copy() if song else Timeline()
        self._song_end = song.song_end_tick() if song is not None else 0
        self.channel_of_track = {}
        self.setups = {}
        self.mix = {}    # channel -> TrackMix
        self.automation = None   # automation.Player while any track has automation
        self.audio = []  # recordings to play: (start sample, samples, gain, gain, track id, whole, offset, channel)
        sr = float(sample_rate)
        parts = []
        if song is not None:
            audible = {t.id for t in song.audible_tracks()}
            override = effects_override or {}
            effects_used = {}
            for channel, track in enumerate(song.tracks):
                self.channel_of_track[track.id] = channel
                chain = override.get(track.id, getattr(track, "effects", []))
                if getattr(track, "automation", None):
                    effects_used[track.id] = chain
                self.mix[channel] = TrackMix("audio" if track.is_audio else "instrument", track.volume, track.pan,
                                             effects.copy_effects(chain), track.id)
                if track.is_audio:
                    if track.id in audible and (audio_loader is not None or take_loader is not None):
                        loader = take_loader or (lambda t, r: audio_loader(r.take.file) if r.take else None)
                        self._add_audio_track(track, loader, channel)
                    continue
                inst = track.instrument
                # volume and pan are applied after the track's effects (see Engine._mix_channels), so
                # FluidSynth plays every channel at full volume, in the middle
                self.setups[channel] = ChannelSetup(inst.bank, inst.program, inst.is_drum_kit, 127, 64)
                if track.id not in audible:
                    continue
                if notes_by_track is not None and track.id in notes_by_track:
                    notes = notes_by_track[track.id]
                else:
                    notes = track.notes
                    muted = [(r.start, r.end) for r in track.note_regions if r.mute]
                    if muted:  # muted regions stay quiet
                        notes = [n for n in notes if not any(a <= n.tick < b for a, b in muted)]
                if not notes:
                    continue
                ticks = np.array([n.tick for n in notes], dtype=np.float64)
                ends = ticks + np.array([n.length for n in notes], dtype=np.float64)
                on = np.round(self.timeline.ticks_to_seconds_array(ticks) * sr).astype(np.int64)
                off = np.round(self.timeline.ticks_to_seconds_array(ends) * sr).astype(np.int64)
                off = np.maximum(off, on + 1)
                pitches = np.array([n.pitch for n in notes], dtype=np.int64)
                off = end_at_restrike(on, off, pitches)
                vels = np.array([n.velocity for n in notes], dtype=np.int64)
                count = len(notes)
                chans = np.full(count, channel, dtype=np.int64)
                parts.append((on, np.ones(count, np.int64), chans, pitches, vels))
                parts.append((off, np.zeros(count, np.int64), chans, pitches, np.zeros(count, np.int64)))
        if parts:
            samples = np.concatenate([p[0] for p in parts])
            kinds = np.concatenate([p[1] for p in parts])
            order = np.lexsort((kinds, samples))  # note-offs before note-ons at the same sample
            self.samples = samples[order]
            self.kinds = kinds[order]
            self.channels = np.concatenate([p[2] for p in parts])[order]
            self.pitches = np.concatenate([p[3] for p in parts])[order]
            self.velocities = np.concatenate([p[4] for p in parts])[order]
            self.end_sample = int(self.samples[-1])
        else:
            self.samples = self.kinds = self.channels = self.pitches = self.velocities = np.zeros(0, np.int64)
            self.end_sample = 0
        if self.audio:
            self.end_sample = max(self.end_sample, max(part[0] + len(part[1]) for part in self.audio))
        if song is not None and effects_used:
            player = automation_module.Player(song, effects_used)
            self.automation = None if player.empty else player

    def _add_audio_track(self, track, take_loader, channel):
        """Add the parts of the track's recordings that are heard: where recordings overlap,
        the newest (highest layer) plays, and an older one plays again where it ends.
        The track's volume and pan are applied later, after its effects."""
        from . import arrangement

        placed = []
        song_end = self._song_end
        for order, region in enumerate(track.regions):
            if region.mute:
                continue
            take = region.take
            data = take_loader(track, region) if take is not None else None
            if data is None or not len(data):
                continue
            data = data[region.offset:]                       # trimmed at the start
            if region.length:
                data = data[:region.length]                   # and at the end
            if not len(data):
                continue
            if self.sample_rate != AUDIO_RATE:  # exporting at another sample rate
                data = audiotracks.resample(data, AUDIO_RATE, self.sample_rate).astype(np.float32)
            start = self.tick_to_sample(region.tick)
            gain = 10.0 ** (region.gain_db / 20.0)
            count, stop = arrangement.audio_region_repeats(track, order, self.timeline, song_end)
            stop_sample = self.tick_to_sample(stop)
            for k in range(count):                            # a looped recording plays again and again
                begin = start + k * len(data)
                if begin >= stop_sample and k:
                    break
                piece = data[:max(0, stop_sample - begin)] if (k or count > 1) else data
                if len(piece):
                    placed.append((region.layer, order + k * 1e-3, begin, piece, gain))
        covered = []  # sample ranges already taken by newer recordings
        for _layer, _order, start, data, gain in sorted(placed, key=lambda p: (p[0], p[1]), reverse=True):
            end = start + len(data)
            for a, b in _uncovered(start, end, covered):
                # (song sample where this part starts, its samples, gain, gain, track, the whole
                # recording, offset into it, channel)
                self.audio.append((a, data[a - start:b - start], gain, gain, track.id, data, a - start, channel))
            covered.append((start, end))
        self.audio.sort(key=lambda part: part[0])

    def tick_to_sample(self, tick):
        return int(round(self.timeline.tick_to_seconds(tick) * self.sample_rate))

    def sample_to_tick(self, sample):
        return self.timeline.seconds_to_tick(sample / float(self.sample_rate))


def end_at_restrike(on, off, pitches):
    """Note-off samples, each moved no later than the next note-on of the same pitch on the track.

    FluidSynth ends a note when its key is struck again, and the first note's own note-off, coming later, then
    stopped the second note early (found in the review of 9 Oct 2026: notes overlapping after quantizing, pasting,
    editing in the event list or looping a region cut each other short). Of two notes of the same pitch starting
    together, the longer one plays."""
    if len(on) < 2:
        return off
    order = np.lexsort((off, on, pitches))           # by pitch, then start, then end: the longest last
    ends = off[order]
    same = pitches[order][1:] == pitches[order][:-1]
    following = on[order][1:]
    trimmed = ends.copy()
    trimmed[:-1] = np.where(same & (ends[:-1] > following), following, ends[:-1])
    result = np.empty_like(off)
    result[order] = trimmed
    return result


def make_click(sample_rate, accent):
    """A short wooden-sounding click. Accented clicks are higher and louder."""
    length = int(0.035 * sample_rate)
    t = np.arange(length) / float(sample_rate)
    freq = 1760.0 if accent else 1320.0
    env = np.exp(-t * 90.0)
    tone = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2.01 * t)
    level = 0.55 if accent else 0.38
    mono = (tone * env * level / 1.3).astype(np.float32)
    return np.stack([mono, mono], axis=1)


class Recorder:
    """Collects the notes you play while recording."""

    def __init__(self, track_id, channel, start_tick):
        self.track_id = track_id
        self.channel = channel
        self.start_tick = int(start_tick)
        self.pending = {}
        self.notes = []

    def note_on(self, pitch, velocity, tick):
        tick = int(round(tick))
        if tick < self.start_tick - RECORD_GRACE_TICKS:
            return False
        tick = max(tick, self.start_tick)
        if pitch in self.pending:  # same key struck again before release
            self.note_off(pitch, tick)
        self.pending[pitch] = (tick, velocity)
        return True

    def note_off(self, pitch, tick):
        started = self.pending.pop(pitch, None)
        if started is None:
            return
        start, velocity = started
        length = max(MIN_RECORDED_LENGTH, int(round(tick)) - start)
        self.notes.append(Note(start, length, pitch, velocity))

    def finish(self, tick):
        for pitch in list(self.pending):
            self.note_off(pitch, tick)
        self.notes.sort(key=lambda n: (n.tick, n.pitch))
        return self.notes


def _uncovered(start, end, covered):
    """The parts of [start, end) that none of the `covered` ranges overlap."""
    parts = [(start, end)]
    for c0, c1 in covered:
        next_parts = []
        for a, b in parts:
            if c1 <= a or c0 >= b:
                next_parts.append((a, b))
                continue
            if a < c0:
                next_parts.append((a, c0))
            if c1 < b:
                next_parts.append((c1, b))
        parts = next_parts
    return [(a, b) for a, b in parts if b > a]


FADE_FRAMES = 64   # recordings fade in and out over 1.3 ms where they start, stop or are cut, so nothing clicks


class AudioTape:
    """The microphone recording for one take, kept as one continuous piece.

    The first block that arrives says which song sample the performer was hearing,
    which places the take on the beat (the sound card delays are taken into account).
    After that the audio is simply appended, so loop passes can be cut apart later.
    """

    def __init__(self, track_id, start_sample):
        self.track_id = track_id
        self.start = int(start_sample)   # nothing before this song sample is kept (the count-in)
        self.first = None                # song sample of the first kept frame
        self.chunks = []

    def add(self, heard_sample, data):
        if self.first is None:
            skip = int(round(self.start - heard_sample))
            if skip >= len(data):
                return  # still in the count-in
            if skip > 0:
                data = data[skip:]
                heard_sample += skip
            self.first = int(round(heard_sample))
        self.chunks.append(np.array(data, dtype=np.float32, copy=True))

    def finish(self):
        """(song sample of the first frame, audio shaped (frames, channels))."""
        if not self.chunks:
            return self.start, np.zeros((0, 1), dtype=np.float32)
        return self.first, np.concatenate(self.chunks)


class Engine:
    def __init__(self, synth, sample_rate=48000):
        self.synth = synth
        self.sample_rate = int(sample_rate)
        self.commands = queue.SimpleQueue()
        self.messages = queue.SimpleQueue()
        self.data = PlaybackData(None, sample_rate)

        # state owned by the audio thread (the user interface only reads it)
        self.position = 0            # song position in samples at the start of the next block
        self.playing = False
        self.recording = False
        self.count_in_end = None     # sample where the count-in finishes
        self.recorder = None

        # settings the user interface may change at any time
        self.metronome_on = True
        self.metronome_volume = 0.7
        self.count_in_bars = 1
        self.master_gain = 1.0
        self.keep_levels = False       # exports: keep each block's frame levels before the clip (self.levels)
        self.levels = None
        self.record_offset_seconds = 0.0     # notes from the musical keyboard
        self.audio_offset_seconds = 0.0      # recordings from the microphone
        self.stop_at_end = True

        # where playback loops, stops or goes quiet (set by the session, in ticks)
        self._loop_ticks = None      # (start, end): loop this range (a section)
        self._end_tick = None        # stop when reaching this tick (end of the song)
        self._mute_from_tick = None  # do not start notes from here on (long takes)
        self._loop = None            # the same three, converted to samples
        self._end_sample = None
        self._mute_from_sample = None

        self.blocks_processed = 0
        self.errors = 0
        self.bad_blocks = 0          # blocks that held NaN or infinity (silenced, and the effects reset)
        self._applied = {}
        self._sounding = set()
        self._clicks = []
        self._scheduled_offs = []
        self._click_accent = make_click(self.sample_rate, True)
        self._click_normal = make_click(self.sample_rate, False)
        self._buffer = np.zeros((0, 2), dtype=np.float32)

        # every channel's own sound (see _mix_channels): two rows per MIDI channel, plus the
        # synthesizer's built-in reverb and chorus
        self.channel_count = int(getattr(synth, "channels", 128))
        self._planar = np.zeros((2 * self.channel_count, 0), dtype=np.float32)
        self._fx = np.zeros((4, 0), dtype=np.float32)
        self._gains = np.ones(2 * self.channel_count)       # each row's gain at the end of the last block
        self._chains = {}                                   # track id -> effects.Chain
        self._context = effects.Context()
        self.automation = None                              # automation.Player (version 0.9), or None

        # measuring the recording delay (latency.py): the clicks and what the microphone heard
        self._probe = None
        self._pending_fonts = []      # SoundFonts waiting for the song to stop before they load
        self._deferred = {}           # channel -> instrument whose samples load when the song stops

        # audio input: the microphone (the input stream calls input_chunk from its own thread)
        self.inputs = queue.SimpleQueue()
        self.audio_tape = None        # the take being recorded on an audio track
        self.monitoring = False       # hear the input through the speakers or headphones
        self.monitor_gain = 1.0
        self._monitor = []            # input waiting to be heard
        # Hearing yourself must stay as close to live as the sound card allows (Russell, 8 Oct 2026: "a little
        # delay" while singing). Input arrives in bursts, so a little must wait to be heard, or the sound
        # breaks up; but a hiccup (the audio thread held up for a moment) used to leave extra waiting sound
        # behind for good, up to 0.1 s. Now hearing yourself starts once a block is waiting and waits a
        # block longer after each break-up (so it finds the least that works on this sound card), and once
        # the least sound left waiting over half a second is more than that needs, the extra is skipped
        # with a short crossfade, so the delay settles by itself.
        self._monitor_low = None      # the least sound left waiting after a block, this half second
        self._monitor_played = 0      # frames heard this half second
        self._monitor_prime = None    # sound that must be waiting before hearing yourself (re)starts
        self._monitor_primed = False
        self._monitor_start = None    # the fade-in as hearing yourself starts
        self.monitor_stats = {"blocks": 0, "waiting_frames": 0, "most_waiting": 0, "skips": 0, "skipped_frames": 0,
                              "gaps": 0}

        # the arpeggiator (owned by the audio thread)
        self._clock = 0               # free-running sample counter, for the arpeggiator while stopped
        self._arp = None              # ArpSettings while the arpeggiator is on
        self._arp_channel = 0
        self._arp_held = ()           # notes held down, in the order they were pressed
        self._arp_velocity = 100
        self._arp_steps = 0           # notes played since the keys went down
        self._arp_note = None         # (channel, pitch) of the arpeggio note sounding now
        self._arp_off_at = None       # when that note ends
        self._arp_next = None         # when the next note starts
        self._arp_on_grid = False     # True: the two times above are song ticks; False: free-clock samples
        self._arp_last = None         # last random note (Random avoids repeating it)
        self._rng = random.Random(1)

    # ------------------------------------------------------------------
    # commands (safe to call from any thread)
    # ------------------------------------------------------------------
    def set_data(self, data):
        self.commands.put(("data", data))

    def play(self, from_tick):
        self.commands.put(("play", from_tick))

    def record(self, track_id, from_tick, kind="notes"):
        """kind: "notes" for an instrument track, "audio" to record the microphone."""
        self.commands.put(("record", track_id, from_tick, kind))

    def stop(self):
        self.commands.put(("stop",))

    def locate(self, tick):
        self.commands.put(("locate", tick))

    def note_on(self, channel, pitch, velocity, timestamp=None):
        self.commands.put(("on", channel, pitch, velocity, timestamp))

    def note_off(self, channel, pitch, timestamp=None):
        self.commands.put(("off", channel, pitch, timestamp))

    def audition(self, channel, pitch, velocity, seconds=0.4):
        self.commands.put(("audition", channel, pitch, velocity, seconds))

    def panic(self):
        self.commands.put(("panic",))

    def punch_in(self, track_id, kind="notes"):
        """Start recording right now, while already playing (no count-in)."""
        self.commands.put(("punch", track_id, kind))

    def set_monitoring(self, on):
        self.commands.put(("monitor", bool(on)))

    def input_chunk(self, capture_time, data):
        """From the input stream: audio captured at capture_time (time.perf_counter), shaped (frames, channels)."""
        self.inputs.put((capture_time, data))

    def set_channel_instrument(self, channel, bank, program, drum=False):
        """Used for instrument previews on a spare channel."""
        self.commands.put(("instrument", channel, bank, program, drum))

    def set_region(self, loop=None, end=None, mute_from=None):
        """loop: (start_tick, end_tick) to repeat, or None. end: tick to stop at, or None.
        mute_from: tick after which existing notes stay silent (while recording a long take)."""
        self.commands.put(("region", loop, end, mute_from))

    def set_arpeggiator(self, settings):
        """arpeggiator.ArpSettings to turn the arpeggiator on (or change it), None to turn it off."""
        self.commands.put(("arp_settings", settings))

    def arp_hold(self, channel, notes, velocity, timestamp=None):
        """The notes now held on the musical keyboard, in the order pressed (empty: all released)."""
        self.commands.put(("arp_hold", channel, tuple(notes), velocity, timestamp))

    def load_soundfont(self, path, bank_offset=0):
        """Add a SoundFont (a guitar pack that just finished downloading). It loads while the song is
        stopped, so playback never stalls; then ("soundfont_loaded", path, presets) is sent."""
        self.commands.put(("soundfont", path, bank_offset))

    def measure_delay(self):
        """Play the measuring clicks and record what the microphone hears (see latency.py).
        A ("delay_measured", first sample, audio, click positions) message comes back when done."""
        self.commands.put(("probe",))

    def cancel_measurement(self):
        self.commands.put(("probe_cancel",))

    @property
    def measuring(self):
        return self._probe is not None

    def loop_range(self):
        return self._loop_ticks

    # ------------------------------------------------------------------
    # read-only helpers for the user interface
    # ------------------------------------------------------------------
    def position_tick(self):
        return self.data.sample_to_tick(self.position)

    def in_count_in(self):
        return self.count_in_end is not None and self.position < self.count_in_end

    # ------------------------------------------------------------------
    # the audio block
    # ------------------------------------------------------------------
    def process(self, frames, now=None, dac_delay=0.0):
        """Produce `frames` frames of stereo audio.

        now: time.perf_counter() when the audio device asked for this block.
        dac_delay: seconds until the first sample of this block is heard.
        Both are used to place recorded notes where you heard them.
        """
        try:
            return self._process(frames, now, dac_delay)
        except Exception:  # noqa: BLE001 - the audio thread must never die
            self.errors += 1
            if self.errors <= 5:
                log.exception("Audio block failed")
            out = self._out(frames)
            out.fill(0.0)
            return out

    def _out(self, frames):
        if self._buffer.shape[0] != frames:
            self._buffer = np.zeros((frames, 2), dtype=np.float32)
        if self._planar.shape[1] < frames:
            size = max(frames, 1024)
            self._planar = np.zeros((2 * self.channel_count, size), dtype=np.float32)
            self._fx = np.zeros((4, size), dtype=np.float32)
        return self._buffer

    def _process(self, frames, now, dac_delay):
        if now is None:
            now = time.perf_counter()
        self._take_input(now, dac_delay)       # first, so a take keeps everything up to the moment Stop arrives
        self._apply_commands(now, dac_delay)
        out = self._out(frames)
        out.fill(0.0)
        self._planar[:, :frames] = 0.0
        self._fx[:, :frames] = 0.0
        block_start = self.position
        new_clicks = []
        if self.playing:
            offset = 0
            while offset < frames and self.playing:
                start = self.position
                count = frames - offset
                wrap = False
                if self._loop is not None:
                    loop_start, loop_end = self._loop
                    if loop_start <= start < loop_end and start + count >= loop_end > loop_start:
                        count = loop_end - start
                        wrap = True
                if count > 0:
                    new_clicks += self._play_segment(out, offset, count)
                    offset += count
                if wrap:
                    self._wrap_loop()
                elif self._reached_end():
                    self._stop(announce="end")
            if offset < frames:  # stopped part-way: let notes ring out
                self._render_free(out, offset, frames)
        else:
            self._render_free(out, 0, frames)
        if self._monitor:
            self._play_monitor(out)
        self._mix_channels(out, frames, block_start)
        self._continue_clicks(out, 0)
        for offset, click in new_clicks:
            self._clicks.append([click, 0, self.metronome_volume])
            self._continue_clicks(out, offset, only_last=True)
        self._run_scheduled_offs(frames)
        if self.master_gain != 1.0:
            out *= self.master_gain
        if self._probe is not None:
            self._probe_clicks(out, frames)
        if not np.isfinite(out).all():
            self._silence_bad_numbers(out)
        if self.keep_levels:          # (exports) how loud each frame was before full scale cut it off
            self.levels = np.max(np.abs(out), axis=1) if out.ndim > 1 else np.abs(out)
        np.clip(out, -1.0, 1.0, out=out)
        self._clock += frames
        self.blocks_processed += 1
        return out

    def _silence_bad_numbers(self, out):
        """A block held NaN or infinity (only a broken input could bring one: a sound card's garbage, say). It is
        silenced, and the effects start afresh, since a reverb or delay would otherwise keep the bad number going
        round for good and silence the track (the review of 9 Oct 2026)."""
        np.nan_to_num(out, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        self._chains.clear()
        self._sync_chains(self.data)
        self.bad_blocks += 1
        if self.bad_blocks <= 3:
            log.error("A block of sound held NaN or infinity: it was silenced and the effects were reset")

    def _play_segment(self, out, offset, count):
        """Play `count` frames from the playhead into out[offset:]. Returns new clicks."""
        start = self.position
        end = start + count
        data = self.data
        counting_in = self.count_in_end is not None and start < self.count_in_end
        lo = int(np.searchsorted(data.samples, start, side="left"))
        hi = int(np.searchsorted(data.samples, end, side="left"))
        mute_from = self._mute_from_sample
        events = []  # (offset into this segment, 0 for note off or 1 for note on, what to do)
        for i in range(lo, hi):
            at = int(data.samples[i])
            kind = int(data.kinds[i])
            silent = kind == 1 and ((self.count_in_end is not None and at < self.count_in_end)
                                    or (mute_from is not None and at >= mute_from))
            if not silent:
                events.append((at - start, kind, ("note", kind, int(data.channels[i]), int(data.pitches[i]),
                                                  int(data.velocities[i]))))
        arp = self._arp_grid_events(start, end)
        if arp:
            events.extend(arp)
            events.sort(key=lambda e: (e[0], e[1]))  # note offs before note ons at the same moment
        self._render_events(out, offset, count, events)
        if data.audio:
            self._mix_audio(out, offset, start, end)
        self.position = end
        if counting_in and self.position >= self.count_in_end:
            self.count_in_end = None  # count-in over: later loop passes play normally
        return [(offset + rel, click) for rel, click in self._beat_clicks(start, end)]

    def _render_free(self, out, a, b):
        """Render out[a:b] while the song is not playing (live notes and the arpeggiator still sound)."""
        self._render_events(out, a, b - a, self._arp_free_events(a, b))

    def _render_events(self, out, offset, count, events):
        """Render out[offset:offset+count], doing each event exactly at its own sample."""
        cursor = 0
        for rel, _order, action in events:
            if rel > cursor:
                self._render(out, offset + cursor, offset + rel)
                cursor = rel
            if action[0] == "note":
                self._fire(action[1], action[2], action[3], action[4])
            else:
                self._arp_fire(action)
        if cursor < count:
            self._render(out, offset + cursor, offset + count)

    def _reached_end(self):
        if self._end_sample is not None:
            return self.position >= self._end_sample
        data = self.data
        return (self.stop_at_end and not self.recording and len(data.samples) > 0
                and self.position > data.end_sample + END_OF_SONG_SECONDS * self.sample_rate)

    def _wrap_loop(self):
        """The playhead reached the end of the looped section: go back to its start."""
        loop_start, loop_end = self._loop
        self._release_playback_notes()
        start_tick, end_tick = self._loop_ticks
        self._arp_resync(end_tick)  # an arpeggio note still sounding ends with this pass
        if self.recorder is not None:
            notes = self.recorder.finish(end_tick)
            self.messages.put(("recorded", self.recorder.track_id, notes, True))
            self.recorder = Recorder(self.recorder.track_id, self.recorder.channel, start_tick)
        self.position = loop_start

    def _render(self, out, a, b):
        """Render frames a to b of every channel into its own rows (mixed in _mix_channels)."""
        if b > a:
            self.synth.render_channels(b - a, self._planar, a, self._fx)

    # -- mixing: each track through its effects, then its volume and pan -------
    def _mix_channels(self, out, frames, block_start):
        """Add every channel to `out`: through its track's effects, then its volume and pan.

        Gains move in a straight line across the block when they change (a fader or an automation
        step never clicks). Channels that belong to no track (the instrument preview) play as they are."""
        planar = self._planar[:, :frames]
        fx = self._fx[:, :frames]
        out[:, 0] += fx[0] + fx[2]
        out[:, 1] += fx[1] + fx[3]
        data = self.data
        start_gains = self._gains
        end_gains = np.ones_like(start_gains)
        automation = self.automation
        tick_to = None
        if automation is not None and data.mix:
            # the block's end: its gains ramp from where the last block ended to here (stopped: the playhead)
            tick_to = max(0.0, data.sample_to_tick(self.position))
        for channel, mix in data.mix.items():
            volume, pan = mix.volume, mix.pan
            if tick_to is not None:
                volume, pan = automation.mix_at(mix.track_id, tick_to, volume, pan)
            left, right = track_gains(mix.kind, volume, pan)
            end_gains[2 * channel] = left
            end_gains[2 * channel + 1] = right
        processed = []
        if self._chains:
            bpm = data.timeline.tempo_at_tick(max(0.0, data.sample_to_tick(self.position)))
            self._context.bpm = bpm
            for channel, mix in data.mix.items():
                chain = self._chains.get(mix.track_id)
                if chain is None or not chain.active:
                    continue
                if tick_to is not None:
                    automation.apply_effects(mix.track_id, chain, tick_to)
                block = planar[2 * channel:2 * channel + 2].T
                result = chain.process(block, self._context)
                rows = slice(2 * channel, 2 * channel + 2)
                gains = dsp_ramp_pair(start_gains[rows], end_gains[rows], frames)
                out += (result * gains).astype(np.float32)
                processed.append(channel)
        if processed:
            rows = np.array([r for c in processed for r in (2 * c, 2 * c + 1)])
            start_used, end_used = start_gains.copy(), end_gains.copy()
            start_used[rows] = 0.0
            end_used[rows] = 0.0
        else:
            start_used, end_used = start_gains, end_gains
        left_rows, right_rows = planar[0::2], planar[1::2]
        left = start_used[0::2] @ left_rows
        right = start_used[1::2] @ right_rows
        if not np.array_equal(start_used, end_used):
            t = (np.arange(1, frames + 1) / float(frames))
            left = left + ((end_used[0::2] @ left_rows) - left) * t
            right = right + ((end_used[1::2] @ right_rows) - right) * t
        out[:, 0] += left
        out[:, 1] += right
        self._gains = end_gains

    def _sync_chains(self, new):
        """After new playback data: every track gets the effects it has now; a track whose effects
        are unchanged keeps its sound (a reverb tail carries on)."""
        wanted = {}
        for mix in new.mix.values():
            if any(e.get("on", True) and e["type"] in effects.PROCESSORS for e in mix.effects):
                wanted[mix.track_id] = mix.effects
        for track_id in list(self._chains):
            if track_id not in wanted:
                del self._chains[track_id]
        for track_id, chain_effects in wanted.items():
            chain = self._chains.get(track_id)
            if chain is None:
                chain = self._chains[track_id] = effects.Chain(self.sample_rate)
            chain.configure(chain_effects)

    def _fire(self, kind, channel, pitch, velocity):
        if kind == 1:
            self.synth.noteon(channel, pitch, velocity)
            self._sounding.add((channel, pitch))
        else:
            self.synth.noteoff(channel, pitch)
            self._sounding.discard((channel, pitch))

    # -- commands ---------------------------------------------------------
    def _would_stall(self, setup):
        check = getattr(self.synth, "would_load_samples", None)
        return bool(check and check(setup.bank, setup.program))

    def _apply_commands(self, now, dac_delay):
        if self._pending_fonts and not self.playing:
            self._load_fonts()
        if self._deferred and not self.playing:
            deferred, self._deferred = self._deferred, {}
            for channel, setup in deferred.items():
                if self._applied.get(channel) == setup:
                    self.synth.set_instrument(channel, setup.bank, setup.program, setup.drum)
        while True:
            try:
                cmd = self.commands.get_nowait()
            except queue.Empty:
                return
            kind = cmd[0]
            if kind == "on":
                _, channel, pitch, velocity, stamp = cmd
                self.synth.noteon(channel, pitch, velocity)
                if self.recorder is not None and channel == self.recorder.channel:
                    self.recorder.note_on(pitch, velocity, self._heard_tick(self.position, now, dac_delay, stamp))
            elif kind == "off":
                _, channel, pitch, stamp = cmd
                self.synth.noteoff(channel, pitch)
                if self.recorder is not None and channel == self.recorder.channel:
                    self.recorder.note_off(pitch, self._heard_tick(self.position, now, dac_delay, stamp))
            elif kind == "data":
                self._swap_data(cmd[1])
            elif kind == "play":
                self._start(cmd[1], record_track=None)
            elif kind == "record":
                self._start(cmd[2], record_track=cmd[1], kind=cmd[3] if len(cmd) > 3 else "notes")
            elif kind == "stop":
                self._stop()
            elif kind == "locate":
                self._release_playback_notes()
                if self.playing:
                    self._arp_resync(self._current_tick())
                self.position = self.data.tick_to_sample(cmd[1])
            elif kind == "audition":
                _, channel, pitch, velocity, seconds = cmd
                self.synth.noteon(channel, pitch, velocity)
                self._scheduled_offs.append([int(seconds * self.sample_rate), channel, pitch])
            elif kind == "panic":
                self.synth.all_sounds_off(-1)
                self._sounding.clear()
                self._scheduled_offs.clear()
                self._arp_note = None
                self._arp_held = ()
                self._arp_next = None
            elif kind == "punch":
                self._punch_in(cmd[1], cmd[2] if len(cmd) > 2 else "notes")
            elif kind == "monitor":
                self.monitoring = cmd[1]
                self._monitor_low, self._monitor_played = None, 0
                self._monitor_prime, self._monitor_primed = None, False
                # hearing yourself fades in (20 ms since 21 Oct 2026, was 10) when it starts, even with the microphone
                # already open
                self._monitor_start = StartFade(self.sample_rate, quiet=0, fade=0.02) if self.monitoring else None
                if not self.monitoring:
                    self._monitor.clear()
            elif kind == "instrument":
                _, channel, bank, program, drum = cmd
                self.synth.set_instrument(channel, bank, program, drum)
                self._applied.pop(channel, None)
            elif kind == "region":
                _, self._loop_ticks, self._end_tick, self._mute_from_tick = cmd
                self._region_to_samples()
            elif kind == "arp_settings":
                self._arp = cmd[1]
                if self._arp is None:
                    self._arp_end_note(self._current_tick())
                    self._arp_held = ()
                self._arp_next = None
            elif kind == "probe":
                start = self._clock + int(0.05 * self.sample_rate)
                self._probe = {"clicks": latency.click_times(self.sample_rate, start), "first": None, "chunks": [],
                               "end": start + latency.total_frames(self.sample_rate),
                               "sound": latency.click_sound(self.sample_rate), "playing": []}
            elif kind == "soundfont":
                self._pending_fonts.append(cmd[1:])
                if not self.playing:
                    self._load_fonts()
            elif kind == "probe_cancel":
                self._probe = None
            elif kind == "arp_hold":
                _, channel, notes, velocity, _stamp = cmd
                if channel != self._arp_channel:
                    self._arp_end_note(self._current_tick())
                was_held = bool(self._arp_held)
                self._arp_channel, self._arp_held, self._arp_velocity = channel, notes, velocity
                if not notes:
                    self._arp_end_note(self._current_tick())  # letting go stops the arpeggio at once
                    self._arp_next = None
                elif not was_held:
                    self._arp_steps = 0  # a fresh chord starts from its first note
                    self._arp_next = None

    def _load_fonts(self):
        pending, self._pending_fonts = self._pending_fonts, []
        for path, bank_offset in pending:
            try:
                self.synth.load_soundfont(path, bank_offset)
                presets = self.synth.presets()
                for channel, setup in self._applied.items():   # tracks waiting for it stop using the stand-in
                    if bank_offset and setup.bank == bank_offset:
                        self.synth.set_instrument(channel, setup.bank, setup.program, setup.drum)
                self.messages.put(("soundfont_loaded", path, presets))
            except Exception as exc:  # noqa: BLE001 - everything else keeps working
                self.messages.put(("soundfont_failed", path, str(exc)))

    def _region_to_samples(self):
        data = self.data
        if self._loop_ticks is not None:
            a, b = self._loop_ticks
            self._loop = (data.tick_to_sample(a), data.tick_to_sample(b))
        else:
            self._loop = None
        self._end_sample = data.tick_to_sample(self._end_tick) if self._end_tick is not None else None
        self._mute_from_sample = (data.tick_to_sample(self._mute_from_tick)
                                  if self._mute_from_tick is not None else None)

    def _heard_tick(self, block_start, now, dac_delay, stamp):
        """Song position (in ticks) that was audible when a key was pressed."""
        waited = max(0.0, now - stamp) if stamp is not None else 0.0
        delay = dac_delay + waited + self.record_offset_seconds
        return self.data.sample_to_tick(block_start - delay * self.sample_rate)

    def _swap_data(self, new):
        old = self.data
        if self.playing:
            # keep the same musical position even if tempos changed
            tick = old.sample_to_tick(self.position)
            self.position = new.tick_to_sample(tick)
            if self.count_in_end is not None:
                self.count_in_end = new.tick_to_sample(old.sample_to_tick(self.count_in_end))
            if not _same_notes(old, new):
                self._release_playback_notes()    # (a change of volume, pan or automation leaves notes sounding)
        else:
            self.position = new.tick_to_sample(old.sample_to_tick(self.position))
        self.data = new
        self.automation = new.automation
        self._region_to_samples()
        self._sync_chains(new)
        for channel, setup in new.setups.items():
            if self._applied.get(channel) != setup:
                prev = self._applied.get(channel)
                if prev is None or prev[:3] != setup[:3]:
                    if self.playing and self._would_stall(setup):
                        # a guitar pack's samples take most of a second to load: a stand-in plays until
                        # the song stops, so playback never stutters
                        self.synth.set_instrument(channel, 0, 30, False)
                        self._deferred[channel] = setup
                    else:
                        self.synth.set_instrument(channel, setup.bank, setup.program, setup.drum)
                        self._deferred.pop(channel, None)
                self.synth.cc(channel, 7, setup.volume_cc)
                self.synth.cc(channel, 10, setup.pan_cc)
                self._applied[channel] = setup
        for channel in [c for c in self._applied if c not in new.setups]:
            self.synth.all_notes_off(channel)
            del self._applied[channel]

    def _start(self, from_tick, record_track, kind="notes"):
        self._release_playback_notes()
        self._arp_resync(None)
        self._clicks.clear()
        data = self.data
        start_sample = data.tick_to_sample(from_tick)
        self.count_in_end = None
        self.recorder = None
        self.audio_tape = None
        self.recording = False
        if record_track is not None:
            channel = data.channel_of_track.get(record_track)
            if channel is None:
                self.messages.put(("error", "The track to record on no longer exists"))
                return
            if kind == "audio":
                self.audio_tape = AudioTape(record_track, start_sample)
            else:
                self.recorder = Recorder(record_track, channel, from_tick)
            self.recording = True
            bars = max(0, int(self.count_in_bars))
            if bars:
                tl = data.timeline
                bar = tl.tick_to_bar(from_tick)
                count_in_ticks = tl.bar_to_tick(bar) - tl.bar_to_tick(bar - bars)
                self.count_in_end = start_sample
                start_sample = data.tick_to_sample(from_tick - count_in_ticks)
        self.position = start_sample
        self.playing = True

    def _punch_in(self, track_id, kind="notes"):
        if not self.playing or self.recording:
            return
        channel = self.data.channel_of_track.get(track_id)
        if channel is None:
            self.messages.put(("error", "The track to record on no longer exists"))
            return
        if kind == "audio":
            self.audio_tape = AudioTape(track_id, self.position)
        else:
            tick = max(0, int(round(self.data.sample_to_tick(self.position))))
            self.recorder = Recorder(track_id, channel, tick)
        self.recording = True
        self.count_in_end = None

    def _stop(self, announce=None):
        if not self.playing:
            return
        stop_tick = self.data.sample_to_tick(self.position)
        self._arp_resync(stop_tick)  # ends any arpeggio note while the recorder can still take it
        self.playing = False
        self._release_playback_notes()
        if self.recorder is not None:
            notes = self.recorder.finish(stop_tick)
            self.messages.put(("recorded", self.recorder.track_id, notes, False))
            self.recorder = None
        if self.audio_tape is not None:
            first, audio = self.audio_tape.finish()
            self.messages.put(("audio_recorded", self.audio_tape.track_id, first, audio, self._loop))
            self.audio_tape = None
        self.recording = False
        self.count_in_end = None
        if announce:
            self.messages.put(("stopped", announce))

    def _release_playback_notes(self):
        for channel, pitch in self._sounding:
            self.synth.noteoff(channel, pitch)
        self._sounding.clear()

    def _run_scheduled_offs(self, frames):
        if not self._scheduled_offs:
            return
        keep = []
        for item in self._scheduled_offs:
            item[0] -= frames
            if item[0] <= 0:
                self.synth.noteoff(item[1], item[2])
            else:
                keep.append(item)
        self._scheduled_offs = keep

    # -- audio: recordings, the microphone and monitoring ----------------------
    def _mix_audio(self, out, offset, start, end):
        """Add the recordings that sound between song samples start and end."""
        mute_from = self._mute_from_sample
        quiet_until = self.count_in_end
        recording_on = self.audio_tape.track_id if self.audio_tape is not None else None
        planar = self._planar
        for begin, samples, left, right, track_id, _whole, _skip, channel in self.data.audio:
            if begin >= end:
                break
            if mute_from is not None and begin >= mute_from:
                continue  # later sections stay quiet during a long take
            if track_id == recording_on:
                continue  # the track being recorded is quiet, so its old takes don't get into the microphone
            a, b = max(start, begin), min(end, begin + len(samples))
            if quiet_until is not None:
                a = max(a, quiet_until)  # the count-in plays only clicks
            if a >= b:
                continue
            lo, hi = a - begin, b - begin
            piece = samples[lo:hi]
            count = len(samples)
            if lo < FADE_FRAMES or hi > count - FADE_FRAMES:
                where = np.arange(lo, hi, dtype=np.float32)
                ramp = np.minimum(1.0, np.minimum((where + 1.0) / FADE_FRAMES, (count - where) / FADE_FRAMES))
                piece = piece * ramp[:, None]
            lo_col, hi_col = offset + (a - start), offset + (b - start)
            planar[2 * channel, lo_col:hi_col] += piece[:, 0] * left
            planar[2 * channel + 1, lo_col:hi_col] += piece[:, -1] * right

    def _take_input(self, now, dac_delay):
        """Collect microphone audio: into the take being recorded, and to the speakers when monitoring."""
        while True:
            try:
                captured, data = self.inputs.get_nowait()
            except queue.Empty:
                return
            if self.audio_tape is not None and self.playing:
                # the song sample the performer was hearing when this audio was captured
                heard = (self.position + (captured - (now + dac_delay)) * self.sample_rate
                         - self.audio_offset_seconds * self.sample_rate)
                self.audio_tape.add(heard, data)
            if self._probe is not None:
                # placed on the engine's own clock exactly the same way, without any adjustment
                heard = self._clock + (captured - (now + dac_delay)) * self.sample_rate
                if self._probe["first"] is None:
                    self._probe["first"] = int(round(heard))
                self._probe["chunks"].append(np.array(data, dtype=np.float32, copy=True))
            if self.monitoring:
                start = self._monitor_start
                self._monitor.append(start.apply(data) if start is not None else data)
                while sum(len(m) for m in self._monitor) > self.sample_rate // 10:
                    self._monitor.pop(0)  # never let the monitor fall more than 0.1 s behind

    MONITOR_WINDOW_SECONDS = 0.5
    MONITOR_FADE = 64
    MONITOR_MOST_BLOCKS = 16          # never wait more than this many blocks before hearing yourself

    def _monitor_ready(self, frames):
        """Whether enough sound is waiting to hear yourself without breaking up (see __init__)."""
        if self._monitor_prime is None:
            self._monitor_prime = frames
        if not self._monitor_primed:
            if sum(len(m) for m in self._monitor) < self._monitor_prime:
                return False
            self._monitor_primed = True
        return True

    def _trim_monitor(self, frames, left):
        """After a block: `left` frames are still waiting. Skip what is never needed (see __init__)."""
        stats = self.monitor_stats
        stats["blocks"] += 1
        stats["waiting_frames"] += max(0, left) + frames
        stats["most_waiting"] = max(stats["most_waiting"], max(0, left) + frames)
        self._monitor_low = left if self._monitor_low is None else min(self._monitor_low, left)
        self._monitor_played += frames
        if self._monitor_played < self.MONITOR_WINDOW_SECONDS * self.sample_rate:
            return
        room = max(frames // 2, (self._monitor_prime or frames) - frames)   # what the bursts have needed
        extra = self._monitor_low - room
        self._monitor_low, self._monitor_played = None, 0
        fade = self.MONITOR_FADE
        if extra < fade or left < extra + fade:
            return
        joined = np.concatenate(self._monitor)
        ramp = (np.arange(fade, dtype=np.float32) + 0.5)[:, None] / fade
        kept = joined[extra:].copy()
        kept[:fade] = joined[:fade] * (1.0 - ramp) + kept[:fade] * ramp    # no click where sound is skipped
        self._monitor = [kept]
        stats["skips"] += 1
        stats["skipped_frames"] += extra

    def monitor_report(self):
        """How close to live hearing yourself stayed, in words for the log (and resets the counts)."""
        stats = self.monitor_stats
        if not stats["blocks"]:
            return ""
        ms = 1000.0 / self.sample_rate
        text = ("on average {:.1f} ms of sound waited to be heard (at most {:.1f} ms); {} catch-up{} skipped {:.1f} ms in "
                "all; the input fell behind {} time{}").format(
            stats["waiting_frames"] / float(stats["blocks"]) * ms, stats["most_waiting"] * ms, stats["skips"],
            "" if stats["skips"] == 1 else "s", stats["skipped_frames"] * ms, stats["gaps"],
            "" if stats["gaps"] == 1 else "s")
        for key in stats:
            stats[key] = 0
        return text

    def _play_monitor(self, out):
        """What the microphone hears, through the track being recorded (its effects, volume and pan),
        or straight to the speakers when no track is recording."""
        frames, position = out.shape[0], 0
        if not self._monitor_ready(frames):
            return
        channel = None
        if self.audio_tape is not None:
            channel = self.data.channel_of_track.get(self.audio_tape.track_id)
        while self._monitor and position < frames:
            chunk = self._monitor[0]
            take = min(len(chunk), frames - position)
            if channel is None:
                out[position:position + take, 0] += chunk[:take, 0] * self.monitor_gain
                out[position:position + take, 1] += chunk[:take, -1] * self.monitor_gain
            else:
                self._planar[2 * channel, position:position + take] += chunk[:take, 0] * self.monitor_gain
                self._planar[2 * channel + 1, position:position + take] += chunk[:take, -1] * self.monitor_gain
            if take < len(chunk):
                self._monitor[0] = chunk[take:]
            else:
                self._monitor.pop(0)
            position += take
        if position < frames:
            # the microphone fell behind and the sound broke up: wait for a block more before going on
            self.monitor_stats["gaps"] += 1
            self._monitor_primed = False
            self._monitor_prime = min(self._monitor_prime + frames, self.MONITOR_MOST_BLOCKS * frames)
            self._monitor_low, self._monitor_played = None, 0
            return
        self._trim_monitor(frames, sum(len(m) for m in self._monitor))

    def _probe_clicks(self, out, frames):
        """The measuring clicks (on the engine's own clock), and the end of the measurement."""
        probe = self._probe
        sound = probe["sound"]
        start, end = self._clock, self._clock + frames
        for click in probe["clicks"]:
            if click + len(sound) <= start or click >= end:
                continue
            a = max(click, start)
            b = min(click + len(sound), end)
            out[a - start:b - start] += sound[a - click:b - click]
        if end >= probe["end"]:
            audio = (np.concatenate(probe["chunks"]) if probe["chunks"]
                     else np.zeros((0, 1), dtype=np.float32))
            first = probe["first"] if probe["first"] is not None else start
            self.messages.put(("delay_measured", first, audio, list(probe["clicks"])))
            self._probe = None

    # -- the arpeggiator -----------------------------------------------------
    def _current_tick(self):
        """The song position now while playing (to end arpeggio notes cleanly), else None."""
        return self.data.sample_to_tick(self.position) if self.playing else None

    def _arp_active(self):
        return self._arp is not None and (bool(self._arp_held) or self._arp_note is not None)

    def _arp_resync(self, tick):
        """Playing started or stopped, or the playhead jumped: end the sounding note and plan again."""
        self._arp_end_note(tick)
        self._arp_next = None
        self._arp_on_grid = False

    def _arp_end_note(self, tick=None):
        """Stop the arpeggio note sounding now (recorded as ending at `tick` while recording)."""
        if self._arp_note is None:
            return
        channel, pitch = self._arp_note
        self._arp_note = None
        self._arp_off_at = None
        self.synth.noteoff(channel, pitch)
        if tick is not None and self.recorder is not None and channel == self.recorder.channel:
            self.recorder.note_off(pitch, tick)

    def _arp_pick(self):
        """The next note of the arpeggio."""
        notes = arpeggiator.sequence(self._arp_held, self._arp.pattern, self._arp.octaves)
        if not notes:
            return None
        if self._arp.pattern == "Random":
            pitch = self._rng.choice([n for n in notes if n != self._arp_last] or notes)
        else:
            pitch = notes[self._arp_steps % len(notes)]
        self._arp_steps += 1
        self._arp_last = pitch
        return pitch

    def _arp_grid_events(self, start, end):
        """Arpeggio notes between song samples start and end, exactly on the beat grid."""
        if not self._arp_active():
            return []
        if not self._arp_on_grid:  # coming from the free clock: start planning on the grid
            self._arp_end_note(None)
            self._arp_next = None
            self._arp_on_grid = True
        data = self.data
        step = self._arp.step_ticks
        if self._arp_held and self._arp_next is None:
            self._arp_next = math.ceil(data.sample_to_tick(start) / step - 1e-6) * step
        events = []
        while True:
            off_at = data.tick_to_sample(self._arp_off_at) if self._arp_note is not None else None
            on_at = (data.tick_to_sample(self._arp_next)
                     if self._arp_held and self._arp_next is not None else None)
            if off_at is not None and off_at < end and (on_at is None or off_at <= on_at):
                events.append((max(0, off_at - start), 0, ("arp_off",) + self._arp_note + (self._arp_off_at,)))
                self._arp_note = None
                self._arp_off_at = None
                continue
            if on_at is None or on_at >= end:
                break
            tick = self._arp_next
            if self._arp_note is not None:  # the previous note is still on: it ends right here
                events.append((max(0, on_at - start), 0, ("arp_off",) + self._arp_note + (tick,)))
                self._arp_note = None
            pitch = self._arp_pick()
            self._arp_next = tick + step
            if pitch is None:
                continue
            events.append((max(0, on_at - start), 1, ("arp_on", self._arp_channel, pitch, self._arp_velocity, tick)))
            self._arp_note = (self._arp_channel, pitch)
            self._arp_off_at = tick + self._arp.gate * step
        return events

    def _arp_free_events(self, a, b):
        """Arpeggio notes for out[a:b] while the song is stopped, on the arpeggiator's own clock."""
        if not self._arp_active():
            return []
        if self._arp_on_grid:
            self._arp_end_note(None)
            self._arp_next = None
            self._arp_on_grid = False
        t0, t1 = self._clock + a, self._clock + b
        step = self._arp_step_samples()
        if self._arp_held and self._arp_next is None:
            self._arp_next = float(t0)  # the first note sounds straight away
        events = []
        while True:
            off_at = self._arp_off_at if self._arp_note is not None else None
            on_at = self._arp_next if self._arp_held and self._arp_next is not None else None
            if off_at is not None and off_at < t1 and (on_at is None or off_at <= on_at):
                events.append((max(0, int(off_at) - t0), 0, ("arp_off",) + self._arp_note + (None,)))
                self._arp_note = None
                self._arp_off_at = None
                continue
            if on_at is None or on_at >= t1:
                break
            at = int(on_at)
            if self._arp_note is not None:
                events.append((max(0, at - t0), 0, ("arp_off",) + self._arp_note + (None,)))
                self._arp_note = None
            pitch = self._arp_pick()
            self._arp_next = on_at + step
            if pitch is None:
                continue
            events.append((max(0, at - t0), 1, ("arp_on", self._arp_channel, pitch, self._arp_velocity, None)))
            self._arp_note = (self._arp_channel, pitch)
            self._arp_off_at = on_at + self._arp.gate * step
        return events

    def _arp_step_samples(self):
        """Samples between arpeggio notes, at the tempo where the playhead is."""
        bpm = self.data.timeline.tempo_at_tick(max(0.0, self.data.sample_to_tick(self.position)))
        return self._arp.step_ticks / float(PPQ) * 60.0 / bpm * self.sample_rate

    def _arp_fire(self, action):
        """Sound (and, while recording, record) one arpeggio note on or off."""
        if action[0] == "arp_on":
            _, channel, pitch, velocity, tick = action
            self.synth.noteon(channel, pitch, velocity)
            if tick is not None and self.recorder is not None and channel == self.recorder.channel:
                self.recorder.note_on(pitch, velocity, tick)
        else:
            _, channel, pitch, tick = action
            self.synth.noteoff(channel, pitch)
            if tick is not None and self.recorder is not None and channel == self.recorder.channel:
                self.recorder.note_off(pitch, tick)

    # -- metronome --------------------------------------------------------
    def _beat_clicks(self, start, end):
        """Clicks for beats in [start, end): a list of (offset from start, click sound)."""
        in_count_in = self.count_in_end is not None and start < self.count_in_end
        if not (self.metronome_on or in_count_in):
            return []
        data = self.data
        tl = data.timeline
        sr = float(self.sample_rate)
        t0 = int(math.floor(tl.seconds_to_tick(start / sr))) - 1
        t1 = int(math.ceil(tl.seconds_to_tick(end / sr))) + 1
        clicks = []
        for tick, _bar, _beat, downbeat in tl.beats_between(t0, t1):
            sample = data.tick_to_sample(tick)
            if not start <= sample < end:
                continue
            counting = self.count_in_end is not None and sample < self.count_in_end
            if not (self.metronome_on or counting):
                continue
            clicks.append((sample - start, self._click_accent if downbeat else self._click_normal))
        return clicks

    def _continue_clicks(self, out, offset, only_last=False):
        frames = out.shape[0]
        items = self._clicks[-1:] if only_last else self._clicks
        for item in items:
            click, pos, volume = item
            room = frames - offset
            take = min(room, click.shape[0] - pos)
            if take > 0:
                out[offset:offset + take] += click[pos:pos + take] * volume
                item[1] = pos + take
        self._clicks = [c for c in self._clicks if c[1] < c[0].shape[0]]


def _same_notes(old, new):
    """True if two playback datas play exactly the same notes at the same moments."""
    return (old.timeline.to_dict() == new.timeline.to_dict()
            and all(np.array_equal(getattr(old, name), getattr(new, name))
                    for name in ("samples", "kinds", "channels", "pitches", "velocities")))


def _contiguous_view(out, a, b):
    """Rows a..b of a C-contiguous (frames, 2) array are themselves contiguous."""
    return out[a:b]


def dsp_ramp_pair(start, end, frames):
    """(frames, 2) gains moving in a straight line from start (left, right) to end over a block."""
    start = np.asarray(start, dtype=np.float64)
    end = np.asarray(end, dtype=np.float64)
    if np.array_equal(start, end):
        return end[None, :]
    t = (np.arange(1, frames + 1) / float(frames))[:, None]
    return start[None, :] + (end - start)[None, :] * t


def fade_gains(positions, end, length):
    """The fade-out's loudness at sample positions: 1 before it, falling to 0 at `end` over `length` samples. The
    curve is (1 - x) squared: halfway through it is 12 dB down, and it keeps getting softer evenly to the ear, where
    a straight line would hardly change at first and then drop off at the very end."""
    start = end - length
    x = np.clip((positions - start + 0.5) / float(max(1, length)), 0.0, 1.0)
    return (1.0 - x) ** 2


def render_offline(song, synth, sample_rate=48000, block_frames=4096, tail_seconds=3.0,
                   progress=None, cancelled=None, audio_loader=None, until_silent=False, take_loader=None,
                   notes_by_track=None, fade_seconds=0.0, on_levels=None):
    """Yield blocks of the whole song: from bar 1 to the end of its last section (or its last
    note, whichever is later), plus a tail so reverb and held notes can ring out.

    tail_seconds: the longest tail (0 ends exactly at the end of the song). until_silent: stop
    the tail as soon as the sound has faded to silence, and leave out the silence.
    Used for WAV export. The metronome is off. `progress(fraction)` is called
    now and then; if `cancelled()` returns True the export stops.
    fade_seconds: a fade-out over the song's last seconds, ending where the song ends (Russell, 21 Oct 2026); the
    whole song fades when it is shorter. Everything after the end is silent, so there is no ring-out with it.
    on_levels(levels): called before each block is yielded with how loud each of its frames was before full scale
    cut it off (a block is never louder than full scale; this says by how much it would have been).
    """
    if fade_seconds > 0:
        tail_seconds, until_silent = 0.0, False
    engine = Engine(synth, sample_rate)
    engine.metronome_on = False
    engine.stop_at_end = False
    engine.keep_levels = on_levels is not None
    engine.set_data(PlaybackData(song, sample_rate, audio_loader, take_loader=take_loader,
                                 notes_by_track=notes_by_track))
    engine.play(0)
    data_end = None
    total = None
    done = 0
    quiet = []           # tail blocks of silence, held back in case the sound comes back
    quiet_frames = 0
    while True:
        block = engine.process(block_frames)
        if data_end is None:
            song_end = engine.data.tick_to_sample(song.song_end_tick()) if hasattr(song, "song_end_tick") else 0
            data_end = max(engine.data.end_sample, song_end)
            total = data_end + int(tail_seconds * sample_rate)
        block = block[:max(0, total - done)].copy()
        levels = engine.levels[:len(block)].copy() if on_levels is not None and engine.levels is not None else None
        start = done
        done += len(block)
        if fade_seconds > 0 and len(block):
            length = min(data_end, int(round(fade_seconds * sample_rate)))
            gains = fade_gains(np.arange(start, done, dtype=np.float64), data_end, length)
            block = (block * gains[:, None]).astype(block.dtype, copy=False)
            if levels is not None:
                levels = levels * gains
        if progress is not None:
            progress(min(1.0, done / float(max(1, total))))
        if until_silent and start >= data_end:
            if len(block) and float(np.max(np.abs(block))) < SILENCE_LEVEL:
                quiet.append((block, levels))
                quiet_frames += len(block)
                if quiet_frames >= SILENCE_SECONDS * sample_rate:
                    return  # faded out: the held-back silence is left out
            else:
                for held, held_levels in quiet:
                    if held_levels is not None:
                        on_levels(held_levels)
                    yield held
                quiet, quiet_frames = [], 0
                if levels is not None:
                    on_levels(levels)
                yield block
        elif len(block):
            if levels is not None:
                on_levels(levels)
            yield block
        if cancelled is not None and cancelled():
            return
        if done >= total:
            return


SILENCE_LEVEL = 10 ** (-80 / 20.0)   # quieter than -80 dB counts as silence
SILENCE_SECONDS = 0.2                 # this much silence after the end means the ring-out is over
