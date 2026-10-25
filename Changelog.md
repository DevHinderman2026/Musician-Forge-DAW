# Musician Forge release notes

## 0.9.11 (25 October 2026, in testing)

### New features and improvements

- Reforge while the song plays: the song keeps playing from where it is, and the new performance comes in at once,
  so you can try one performance after another and hear each in place. The playhead no longer jumps back to the
  region's start. When the song is stopped, Reforge plays the region from its start, as before (Play the region
  after Reforge).
- Notes that are sounding keep sounding through a change made while the song plays: a tempo change, a Reforge or any
  edit. A held chord or a long bass note goes on with no new attack and no gap; a note the change takes away stops,
  and a note it brings in starts at once if enough of it is left (a tenth of a second), so there is never a blip.
- When the whole song has played to its end (All sections on), it stops there and stays there: Musician Forge says
  "End of song, stopped" and where the song ends (in a 16-bar song, "Bar 17, beat 1"), and Space, or Record, starts
  again from the start of the song. A project saved there opens there. (In 0.9.10 the playhead went back to the
  start at once.) Playing one region through still puts the playhead back at that region's start.
- Adding a tempo, time signature, key or chord change, or an automation point, where one already is asks first, for
  example "There is already a tempo change at bar 5, beat 1 (90 BPM). Replace it?". Yes replaces it (one Control+Z
  brings it back); No, or Escape, brings the Add window back with what you typed still in it. Editing a change in
  place does not ask.
- Every Yes or No question can now be answered No with Escape. Windows cannot close a box that has only Yes and No
  buttons with Escape, so until now each one had to be answered. (The question about recovering a project after a
  crash still has to be answered, since No throws the recovered project away.)
- Importing a big MIDI file shows a progress window while the file is read ("Reading the MIDI file", with the
  percentage), as exporting does, and Escape cancels it ("Import cancelled"; nothing changes). A small file shows
  no window.
- Region settings: a trim is said as "Trimmed" first, and then the Regions list reads the region's line once.
- Play keeps the focus where it is in the Recordings and Chord strips windows, so Space there plays and stops.
- Changing an EQ preset, or turning an EQ band on or off, while the song plays now blends over a twentieth of a
  second (it was a hundredth), and quick changes one after another wait for each other, so arrowing through the
  presets never clicks.
- Looping regions:
  - Recording over part of a looping region's repeats replaces only the bars you recorded, and the repeats carry on
    after the recording as the loop would have played them.
  - Adding a section inside a looping region's repeats keeps the loop playing on both sides of the new section.
    Deleting or shortening a section inside it keeps the music on each side.
  - What carries on sounds exactly like the loop: it stays a rhythm player region when it plays the same notes, and
    where a bass, keys, synth or guitar would follow other chords there, it is written out as notes that sound like
    the loop (Musician Forge says so).
  - Turn into notes on a looping region writes out every repeat you hear, as one longer region that no longer
    loops.
  - A looping drummer that is followed by a louder drummer builds into it in its last repeat, as a drummer playing
    once does (new and changed regions).
- Drummers (new and changed regions):
  - The hi-hat pedal waits where the hand plays an open hi-hat, as a drummer's foot is up then; until now the foot
    landed with the open hi-hat on two and four in funk and pop and cut it off at once. A step you set by hand stays
    and the other sound gives way.
  - The shaker, tambourine, cowbell, claves, congas and bongos are a second player's: they always play, are never
    left out for the drummer's two hands, and play on through the drummer's fills. Pop's own tambourine on two and
    four is now heard.
  - In metal variations 3 and 4, which keep time on the crash, the Ride takes over from the crash as the Hi-hat
    does: "Ride on with eighth notes, crash off". The crash comes back once neither the Hi-hat nor the Ride keeps
    time.
  - A drummer that follows another track plays its own groove in a bar where that track plays nothing, instead of
    a few scattered kicks.
- Bass, keys, synth and guitar (new and changed regions):
  - A player that follows another track plays its own part in a bar where that track plays nothing, instead of two
    or three scattered notes.
  - In meters counted in threes (3/8, 6/8, 9/8 and 12/8), the passing note into a chord change comes an eighth
    before it instead of a sixteenth; where the bass already plays that eighth, its own note there leads into the
    new chord.
  - An arpeggio or picked note that a chord change cuts gives way to the new chord at once: the arpeggio's note,
    on the new chord, starts right at the change instead of leaving a gap until the next note.
  - A hand-made step "as the style plays it" plays the style's own notes at the step's loudness even when the
    part's Loudness is 0 (it played the player's main sound instead: a full chord on the keys).
- The guitar sound pack check says what is wrong in plain words when a download is not right.
- Control+Z and Control+Y work inside every list window: Effects, Automation and its points, Tempo changes, Time
  signature changes, Key changes, the Event list, Recordings, Sections and the Chord track. The list is read again at
  once, on the item it was on (or the nearest one), and a window whose track the undo took away closes and says so.
- Hit detection on a long recording (a player following an audio track) needs about half the memory it did.
- Changing a reverb's Room size while the song plays, by hand or with a preset, lets the reverb that is ringing ring
  out by itself, while the sound that comes next goes into the new room; it used to stop dead.
- A song can be at most 9999 bars long, as the bar boxes already were. Once it is, Add section and Duplicate
  section say so ("The song is already 9999 bars long, the longest a song can be, so no section can be added."), a
  section that would only partly fit says how many bars are left, and no other edit can make the song longer: a take
  in an Automatic section stops at the end of bar 9999. A MIDI file's notes past bar 9999 are left out, and the
  import says how many.
- A region set to "Loop until the next region (or the end of the song)" stops where the song ended when you add a
  section at the end, duplicate one to the end, or make the last section longer: the new bars start empty, and a
  duplicated section sounds like the one it copies. A section added in the middle of the song still leaves the loop
  playing on both sides of it.

### Bug fixes

- Fixes a looping player region that the next region cuts short leading back into its own first chord in the last
  repeat you hear, instead of into the region that comes next (new and changed regions).
- Fixes Move region closing its window before it said that the bar does not have the beat you typed: the window now
  stays open with what you typed still in it, as the other windows do.
- Fixes Import MIDI file refusing a MIDI file that holds only a chord track ("has no notes to import"): its chords
  now come into the chord track.
- Fixes making the last section shorter under a looping region: the section grew straight back to hold the whole
  loop. It now stays as long as you set it, and the loop stops at its end.
- Fixes duplicating a section that a looping region plays across: the copy's loop played all its repeats from the
  copy's start and made the song longer. The copy now holds what the loop plays in those bars.
- Fixes playing past the end of the song, or of a region played on its own, by up to a few milliseconds: a note
  starting just after the end blipped, and the metronome clicked once more after the last bar.
- Fixes a held note that could keep sounding until Panic after its track was changed between an instrument and a
  drum kit while the note sounded.
- Fixes recordings on audio tracks clicking when playing stopped, jumped or went round the loop, and when a recording
  was moved, removed, muted or made louder while the song played: they now fade in a thousandth of a second or so,
  as they already did at their own edges. Exports are unchanged.
- Fixes a project with a damaged rhythm player setting not opening at all.
- Fixes a damaged project file that reaches millions of bars freezing Musician Forge as it opened: it is refused as
  damaged, and its backup is offered as usual.
- Fixes a length that ends just before a bar line being said a bar short ("ends at bar 9, 7 bars and 4 beats long"
  for 8 bars).
- Fixes a time signature change making the song longer when a looping region's repeats ran past its end: every
  section keeps its number of bars.
- Fixes the song playing on in silence after the section that was looping was made shorter (in Section settings, or
  by Control+Z) while the playhead was past its new end: it goes round to the section's start.
- Fixes a time signature change moving the playhead into another bar: it stays in its bar, at its place there.
- Fixes a save that Windows refused renaming the song after the file it was not saved in, and saying the refusal as
  "[Errno 13]": it now says in words that the project could not be saved there.
- Fixes Stop after recording past the end of an Automatic section saying "beat 4.999".
- Fixes editing a tempo change that a MIDI import put between beats (bar 2, beat 2.5): the Beat box showed beat 2,
  and changing only the tempo moved the change or refused it. The box now takes decimals.
- Fixes Rename track closing its window when the name was empty: it stays open with what you typed.
- Fixes the keyboard's description in the Scale and Chord strips layouts naming the wrong note for the A key.
- Fixes Move region, with the bar and beat left as shown, moving a region that starts between beats onto the beat.
- Fixes deleting a tempo, time signature or key change landing on the change before it: it lands on the next one,
  as every other list does.
- Fixes Speak note names saying a chord strip of your own without its bass note ("A minor" for "A minor with E in
  the bass").
- Fixes the Hi-hat pedal's Step pattern showing an empty bar when the pedal was turned on in rock, metal or a drum
  machine, though it plays the foot on two and four; setting its steps as shown silenced the foot.
- Fixes importing a MIDI file from programs that start a repeated note before ending the one before it: the
  repeated notes came in as short blips.
- Fixes a track you named "Chord track" coming back from Musician Forge's own MIDI file as chords instead of as its
  notes.
- Fixes a failed export (a full disk, or the old file open in another program) leaving a temporary file beside it.
- Fixes a guitar pack download that is the wrong file being downloaded whole, three times, before it was refused: it
  now stops as soon as its size shows it is wrong, and a full disk is said in words.
- Fixes the Windows voice (when no screen reader is running) reading text that starts with "<" as markup.

### Older projects

- They play the same notes as before; this version's changes to the players come to a region once you change
  something in it.
- A project longer than 9999 bars, which only a damaged file can be, is refused when it opens, and its backup is
  offered.

### New projects

- New and changed rhythm player regions use this version's rules.

## 0.9.10 (25 October 2026, in testing)

### New features and improvements

- A kick under every crash: in every drummer, where the region starts and after every fill, the kick (bass drum)
  lands with the crash cymbal, as a drummer's foot does, even when the Kick piece is turned off (new and changed
  regions). It follows the Crash's When setting (a crash moved to the sections or every few bars brings its kick
  along; Never means none), and a kick you set softly by hand on that beat keeps the loudness you gave it.
- A player following a strummed guitar now hears each strum as one hit, where its first string is, instead of six
  hits a few ticks apart: the bass, keys, synth, pad and the drummer's kick lock to the strum, on the beat (new and
  changed regions).
- When the whole song has played to its end (All sections on), the playhead goes back to the start of the song
  and Musician Forge says so ("End of song, stopped. Bar 1, start of Section 1"), so Space plays it again. Playing
  one region through puts the playhead back at that region's start.
- Changing an EQ preset, or turning an EQ band on or off, while the song plays blends from the old sound to the new
  one over a hundredth of a second instead of jumping.

### Bug fixes

- Fixes the playhead stopping on the very last tick of the song, so that Space played that one tick and said "End of
  song" again, and a project saved there opened at "beat 4.999".
- Fixes Duplicate on a looping region putting the copy inside the region's own repeats, so the region played once
  and the Regions list said it still looped: the copy goes after the repeats.
- Fixes Move region accepting a beat the bar does not have ("bar 1, beat 9" quietly became bar 3): it is refused
  with a message, as a chord change is.
- Fixes adding an automation point at the exact moment of an existing point replacing it without a word: it now
  says "Replaced the point that was there".
- Fixes the pushed pad (synth pad and keys, variation 4) being cut to a sixteenth when the chord track changed to
  that very chord on the last sixteenth of the bar (new and changed regions).
- Fixes hit detection missing most of the hits in a recording that sits off centre (an interface with a DC offset):
  the offset is taken out first.

- Fixes the automation point window closing before it said why a point could not be moved (onto another point, or
  past the lane's limit): the window now stays open with what you typed still in it, like Region settings, so you
  can put the place right.
- Fixes editing a tempo, time signature, key or chord change and moving it onto the bar (and beat) of another one,
  which quietly took that one's place, so a change was lost: the move is refused with a message, and the window
  stays open with what you typed still in it.

### Older projects

- They play the same notes as before; the kick under the crash comes to a region once you change something in it.

### New projects

- New and changed rhythm player regions use this version's rules.

## 0.9.9 (25 October 2026, in testing)

### New features and improvements

- Changing a drummer's style or variation keeps one hand on one cymbal: if the Ride and the Hi-hat would both keep
  time in the new style, the one that kept time before goes on doing it and the other turns off for it ("Hi-hat
  off"), as turning a piece on does. One Control+Z brings back the style as it was.
- A drum piece that is on always plays: turning on a piece the variation's groove has none of (the hi-hat in jazz,
  the snare in house, say) gives it the first of its patterns, eighth notes on the hi-hat, so the jazz Hi-hat turned
  on keeps time and turns the Ride off. The Kit pieces list no longer says "not in this groove"; a piece that is off
  just says "off" (new and changed regions; older projects play as before until you change them).
- Where a metal groove keeps time on the crash (variations 3 and 4), turning the Hi-hat on takes over: the crash's
  groove goes off ("Hi-hat on with eighth notes, crash off"; its line reads "Crash cymbals: off, the hi-hat keeps
  time") and comes back when the Hi-hat is turned off again. The crash where a section starts and after fills stays.
- Every drummer crashes where the region starts and after every fill, jazz and the hand percussion styles too, and
  after fills whatever the Crash's When setting is, unless it is Never. The Crash toggle turns only the groove's own
  crashes on and off (new and changed regions).
- A piece you turn on whose hand-made steps are all silent plays again, a pattern given to a piece that had nothing
  to play gives way to the new groove when you change the style or variation, the pattern given is one your kit has
  the sounds for, and a Pattern that has nothing in it for a piece turns the piece off. The Pattern list no longer
  offers "None in the groove": to take a piece out of the groove, turn it off.
- Two new chord types, minor major seven (mMaj7) and augmented major seven (maj7#5), in the chord windows and the
  chord strips. Chord progressions with sevenths now use the key's own seventh, so harmonic minor, melodic minor,
  Phrygian dominant and Hungarian minor progressions stay in the key (C harmonic minor starts on C minor major
  seven). Working out chords from notes is unchanged.
- A MIDI export with more than one drum track puts each on channel 10 of its own MIDI port, so each keeps its own
  kit, volume, pan and automation.

### Bug fixes

- Fixes older projects (saved before 0.9.8) where the open hi-hat's loudness in Track settings differed from the
  closed hi-hat's: the open hi-hats played at the hi-hat's loudness instead of their own. It is kept now, until you
  change the kit's loudness in Track settings.
- Fixes older projects whose closed and open hi-hats had hand-made steps of different lengths (3 bars and 2 bars,
  say): the open hi-hat drifted out of step after a few bars.
- Fixes older projects with the closed hi-hat turned off but holding hand-made steps: they started to play under an
  open hi-hat that was on.
- Fixes older projects with "foot only" and the closed hi-hat's Pattern set to None: the foot on two and four went
  silent.
- Fixes a project saved by a newer Musician Forge being lost: after opening its backup instead, the second save
  wrote over it in the .bak file. A backup saved by a newer version is never written over now.
- Fixes a take being lost, or going into the next project, when New or Open stopped a recording: the program
  stopped waiting for the take before it arrived.
- Fixes a crash cymbal you turned off yourself coming back on when the Hi-hat was turned off, and a style or
  variation change into a groove that keeps time on the crash leaving the hi-hat and the crash both playing.
- Fixes moving or duplicating a song section before the first chord change: it played the chord where it landed
  instead of its own.
- Fixes chord progressions in Hungarian Minor putting chords with notes outside the key on the chord track.
- Fixes editing an automation point's value moving it onto the point next to it, which was lost; moving a point
  onto another is now refused with a message.
- Fixes effect automation stopping after the sound engine recovered from a glitch.
- Fixes a WAV file with a damaged sample rate using up all the memory or failing with "Something went wrong"; it is
  refused with a plain message.
- Fixes long delay echoes with high feedback being cut off while still heard.
- Fixes the reverb's pre-delay, turned up while playing, bringing back a moment of old audio.
- Fixes an audio export reading the project's live keys for pitch correction while it ran, so a key changed during
  the export, or closing the program, could reach the exported file.

## 0.9.8 (24 October 2026, in testing)

### New features and improvements

- Every drummer's kit has one Hi-hat piece, for the hand: its closed and open sounds together (How open the hi-hat
  is sets which). The separate Open hi-hat piece and its toggle are gone.
- A new Hi-hat pedal piece, for the foot, with its own on and off, which no other piece changes. It plays by itself
  on the jazz, funk and pop drummers (jazz has the foot in its grooves; funk and pop keep a quiet foot on two and
  four) and is off on rock, hard rock, metal and the drum machines until you turn it on. Its Pattern list has the
  foot on two and four, on every beat, and on one and three. In the drum layout, the G key is now called the hi-hat
  pedal (it was the pedal hi-hat).
- On the rock, hard rock, metal, jazz, funk and pop drummers the Ride and the Hi-hat take turns as two plain
  toggles: turning the Ride on (Space, Play this piece, a Pattern or steps) turns the Hi-hat off ("Ride on, hi-hat
  off"), turning the Hi-hat on turns the Ride off ("Hi-hat on, ride off"), and turning the one that took over off
  again brings the other back, so something keeps time ("Ride off, hi-hat on"). A piece you turned off yourself
  stays off. The check box itself changes, and the Kit pieces list says why a piece is off ("Hi-hat: off, the ride
  keeps time"). "Foot only" is gone. Each change is one undo step.
- On those drummers the Ride's window and the Hi-hat's window each have the other's Play check box too, right under
  Play this piece.
- The Hi-hat's Pattern list has three open patterns (open on the and of every beat, on the and of four, on every
  beat), and a variation's hi-hat pattern now brings that variation's open hi-hat with it.
- In the Kit pieces list a piece that is off says why ("Ride: off, the hi-hat keeps time"), not which pattern it
  would play.
- A bass, keys, synth or guitar region that loops leads back into its own first chord at the end of every repeat,
  and only the last repeat leads into the chord that comes after it.
- Projects saved by older versions are brought up to date as they open, one version at a time. Nothing is written
  to the file until you save, and then the file as it was is kept as the .bak. A project saved by a newer Musician
  Forge is not opened: a plain message says to update Musician Forge first, and that the file was not changed.

### Bug fixes

- Fixes a hand-made open hi-hat in a trap drummer's Kit pieces being swallowed by the hi-hat roll on the same steps
  (new and changed regions).
- Fixes a chord change that is not on a sixteenth (beat 1.21, say) making the bass, keys, synth and guitar play a
  blip and then nothing for the rest of the bar: the old chord holds to the next sixteenth and the new one is
  struck there, and a drummer following the chord track kicks there too (new and changed regions).
- Fixes the last bar of a rhythm player region not seeing the chord that comes right after the region: a bass run
  led to the wrong chord, a passing note into it never came, and a pad that pushes the next chord in early pushed
  the old one (new and changed regions).
- Fixes the Kit pieces list working out a piece's new state on its own, so what it said could differ from what
  played: it now reads every piece back after each change.
- Fixes the screen reader being cut off after Back to the pattern, and after Play this piece or a Pattern in a
  piece's window turned the ride or the hi-hat off or back on.
- Fixes editing several rhythm player regions at once putting every change into one undo step: each change is its
  own step again, and still covers every region you chose.
- Fixes a project saved by a newer Musician Forge being lost when you opened its backup instead and saved: the
  newer file is now kept as the backup.
- Fixes Region settings closing when the song refuses a trim (an end that would overlap the next region, say): the
  same window comes back with the bars you typed still in it. A trim that works is read from the Regions list
  once, not said as well.
- Fixes Space (and Select or unselect the track) in Export audio's Tracks to export being said over the list's own
  reading of the track: only the count is added after it, as in the event list.
- Fixes the Mute and Solo check boxes, and the start screen's Open and Remove from list buttons, sending the focus
  on by themselves, unannounced, when they are dimmed under it (Control+Z taking back the only track; Open on a
  recent project whose file has gone): the focus goes to the Tracks list, or to New project, first.
- Fixes a hand-made step for a bass, keys, synth or guitar part (the chord, the root, a power chord) held across a
  chord change going quiet, or ringing the old chord, for the rest of the bar: it is struck again on the new chord
  (new and changed regions).
- Fixes the fills of the bass, keys, synth and guitar: a bass fill is a run that walks up or down the scale into
  the coming chord's root, ending a half step from it (it was a jitter of notes around it); a synth or keys
  arpeggio in sixteenths no longer fills with eighths, leaving a hole; a picked guitar part fills with picked
  notes and a strummed one with fast strums, not with power chords (new and changed regions).
- Fixes a looping rhythm player region that starts before the first chord change not leading back into the key's
  own chord (new and changed regions).
- Fixes Add section, Delete section, Duplicate section and a section's length change putting a chord change into
  the chord track that only repeats the chord already playing ("G major at bar 5, G major at bar 9").
- Fixes a chord change or an automation point accepted at bar 0: the project could not be opened again, or the
  point was dropped without a word. Both are refused with a message.
- Fixes a guitar pack download being installed without checking that the file inside is the expected SoundFont:
  its size and check sum are checked first, and a wrong download is removed and tried again at the next start.

### Older projects

- They play the same notes as before, to the note and to the loudness (checked note for note against 0.9.7 over
  hundreds of drummer regions with every hi-hat setting of before): a region's Closed hi-hat and Open hi-hat
  become its Hi-hat and Hi-hat pedal with the same rhythms (a Closed hi-hat at "foot only" opens as Hi-hat off for
  the ride and the pedal on; an Open hi-hat that played keeps its sound in the Hi-hat, its own loudness included; a
  ride that was off for the hi-hats stays off), and a track's kit-piece loudness for the Closed hi-hat goes to the
  Hi-hat and the pedal both. The one thing not carried over is a Track settings loudness set for the Open hi-hat
  (the Hi-hat's covers its open notes now). Every rhythm player region keeps the rules it was made under until
  you change something in it.
- The Hi-hat pedal does not start playing in an older funk or pop region: only new regions, and regions you change,
  get the quiet foot.

### New projects

- New and changed rhythm player regions use this version's rules, with the musical fixes above.

## 0.9.7 (23 October 2026, in testing)

### New features and improvements

- New track (Control+T, or the New track button) opens a list of the kinds of track: Instrument, Audio, Import file
  and Rhythm player. Enter, a double-click or Choose picks one, and Escape adds nothing. Import file always puts the
  file on a new track, and is now the place to import from: the two Import items left the File menu (Control+Shift+I
  still works). Rhythm player always makes a new track. The separate New audio track and New rhythm player buttons
  are gone from the Track group (Control+U and Control+Shift+R still work).
- A new project starts with no tracks: the New track list opens as soon as the project window shows, so the first
  track is the kind you choose.
- A drummer track's Track settings has a loudness slider for each of the ten kit pieces (kick, snare, ride, hi-hats
  and the rest): 50 as the drummer plays it, 100 the loudest, 0 silent. It is the kit's mix for every region on the
  track, fills included.
- On the rock, hard rock, metal, jazz, funk and pop drummers, the ride and the hi-hats take turns, as one hand keeps
  time on one cymbal: turning the ride on moves the hand from the hi-hats, and the hi-hat's foot pedal keeps playing
  ("Closed hi-hat: foot only"), except on metal and hard rock, where the hi-hats are simply off under the ride. A
  ride with nothing of its own to play takes over the hi-hat's rhythm. Turning a hi-hat on turns the ride off;
  turning one off again brings the other back.
- Setting steps for a kit piece you turned off turns it on.
- The start screen has Open and Remove from list buttons for the Recent projects list.
- The Edit group has Select or unselect and Select all buttons, for the Tracks or Regions list you were in last.
- F2 in the Regions list renames the region; the Track menu item is now Rename track or region.
- Each track's reverb and chorus now follow its volume, pan, fades and effects, so a track turned down is quieter in
  the reverb too.
- When only the Microsoft Store's Python is found, or no suitable Python at all, Install or Update offers to install
  Python 3.14 from python.org for you (press Y), for your Windows user only, with no administrator rights.
- Install or Update uses Python 3.12 to 3.14 (Python 3.15 has no build of the window toolkit yet), says to choose
  Extract All when it is run from inside the zip, and Start says when the last install did not finish.
- What Musician Forge says after you press a button now waits until the screen reader has read the button, and check
  boxes no longer repeat their own state; the shortcuts still say it.
- Messages are also shown on NVDA's braille display.
- The release notes say, for every version, what changed for older projects and what applies to new ones.

### Bug fixes

- Fixes Enter doing nothing in the Kit pieces list of every drummer, and in the tempo, time signature and key
  changes, Event list, Recordings, Sections, Chord track, Effects and Automation lists.
- Fixes the screen reader being cut off right after pressing a button or check box, such as Metronome.
- Fixes messages being lost when a window opens or closes or a list is filled again (opening a project, missing
  recordings, a new project, saving on close, recovery, imports), and double speech in the Event list, Effects,
  Recordings, the Step pattern and Kit pieces.
- Fixes the focus jumping when a button dims itself, Yes and No questions belonging to the wrong window, and errors
  and export results being said and then shown in a box: the box alone says them.
- Fixes a track's volume, pan, fades and effects not reaching the reverb and chorus: a silent track's reverb could
  still be heard.
- Fixes exports starting about a tenth of a second too loud, and a click when an EQ band turned on or off.
- Fixes recordings drifting after the microphone briefly dropped out.
- Fixes a stutter when previewing a guitar pack while playing or choosing a drum kit for the first time.
- Fixes automation not moving when sections are added, deleted, moved, copied or resized.
- Fixes Delete removing the wrong regions after another edit.
- Fixes notes lost or recorded on the wrong track when a track was added, moved or duplicated while recording.
- Fixes a take wiping a whole section's rhythm player and unmuting muted bars: it covers only the bars recorded and
  says when it replaced a rhythm player.
- Fixes the playhead jumping back when recording was stopped during the count-in.
- Fixes undo steps mixing during a looping take, edits that change nothing adding an undo step, and importing audio
  onto a new track taking two undo steps.
- Fixes a stuck note after opening a menu while holding a key, and held Space, R, Enter, Escape and B toggling again
  and again.
- Fixes Status not following the Keyboard menu and losing your reading place when it updates.
- Fixes tracks and regions being read twice when typing their number.
- Fixes Alt+Enter and other modified keys on a list running the plain key's action.
- Fixes F2 in the Regions list renaming the track.
- Fixes edit windows losing what you typed when they reopen after a mistake.
- Fixes F6 from Customize chord strips going to the wrong place, and two quick F6 presses saying an area passed by.
- Fixes Quantize leaving out notes near the end of a bar, especially in odd meters such as 7/8.
- Fixes a loop of three or more rhythm players following one another stopping playback and export.
- Fixes crash recovery offering a project you chose not to save, and copied recordings being lost in a new project.
- Fixes MIDI export losing the exact key of a late key change, letters such as curly apostrophes in names, and
  sharing channels between more than 15 tracks.
- Fixes a damaged project with an impossible number not offering its backup.
- Fixes rhythm player regions in new projects or changed in this version: keys and synth chords missing their third
  or seventh, held chords and long notes ringing through a chord change, voicings changing on every note, wrong jazz
  shells, added notes outside the key, guitar chords missing notes, bass notes below the bass, approach notes leading
  to the wrong chord, figures losing notes in 6/8, 12/8 and 7/8, fills starting off the beat in odd meters, the
  hi-hat build over the ride, closed and open hi-hat together, a region that starts or ends partway through a bar.
- Fixes Ember's rolled chords sounding high notes first, and a player following another hearing every note of a
  rolled chord as a hit.
- Fixes the musical keyboard's arpeggiator drifting off the downbeat in odd meters.
- Fixes the installer picking Python 3.15, 3.10 or 3.11, failing for Windows user names with accented letters, Start
  doing nothing after an unfinished install, and some failures reported as success.
- Fixes the rock, hard rock, metal, jazz, funk and pop drummers keeping the ride and the hi-hats going through a
  fill, which took three hands: from the fill's first note to the end of the bar both hands are on the drums, and the
  kick and the hi-hat's foot keep going. A hi-hat build into a louder region stops where a fill starts too.
- Fixes "1 tracks", and the export's distortion warning not telling apart tracks with the same name.

### Older projects

- They play the same notes as before (rhythm player regions keep their old rules until something in the region is
  changed), except in a drummer's fills, where the ride and the hi-hats now stop for the fill.
- Each track's reverb and chorus now follow its volume, so tracks below full volume sound a little drier than before.
- Their drummer tracks get the kit-piece loudness sliders at 50, so nothing changes until you move one; a region that
  set a piece's own loudness keeps it, shown in that piece's window.
- The ride and the hi-hats take turns when you turn one of them on; nothing changes until you do.
- The project file no longer carries a "features" setting written by test builds; it opens as before.

### New projects

- They start with no tracks, and the New track list opens at once.
- New and changed rhythm player regions use this version's rules, with the musical fixes above.

## 0.9.6 (21 October 2026, in testing)

### New features and improvements

- Fill amount now places fills on a steady count of bars, the same for every rhythm player: from 1, every 8th bar;
  from 40, every 4th bar (50 in an 8-bar section fills bars 4 and 8); from 70, every 2nd bar; 100, every bar.
- Fill complexity sets how big each fill is, from a short pickup to a whole bar; Reforge changes the fills' shapes,
  never where they come.
- The acoustic drummers (rock, hard rock, metal, jazz, funk, pop), the hand percussion, the bass, the keys and the
  guitar play with a human feel: a few milliseconds off the grid, straight or swung, with a pocket of their own, such
  as a rock backbeat sitting a little behind the beat. Each Reforge has its own feel.
- When an acoustic drummer rides the crash (a crash on every beat or in eighth notes), the ride and the hi-hat
  played by hand stop, as a real drummer's one hand moves to the crash.
- The drum machines (dubstep, house, trap) and the synth stay exactly on the grid, as machines play.
- A kit piece the variation's groove doesn't use is now off by itself, so the Kit pieces list says what really plays
  (in a rock groove: the ride, crash, toms and congas say "off"). Choosing a pattern or making steps for it turns it
  on, and turning a piece on or off yourself is kept with the project.
- Off takes a piece out of the groove only: fills always use the whole kit, and the crash where a section starts
  follows its When setting.
- The hi-hat plays sixteenth notes at any tempo again, disco sixteenths included (0.9.5 held a drummer's hi-hat to
  eighth notes above 140 beats a minute). The ride still plays eighth notes above 120.
- The Guide for Testers is now a Markdown file (Guide for Testers.md), like the other documents on GitHub, and every
  test is a numbered step with a heading, saying what to check and what to expect; a screen reader moves from step
  to step by heading.
- The Read Me is now README.md, so GitHub shows it on Musician Forge's page: a heading for each section, the piano
  keys in a table, and links to the Guide for Testers, the Credits, the release notes and the License. The words are
  the same. Help, Quick start guide reads it as plain text, as before.
- The Transport, Track, Edit, Region and Song groups are back as buttons in the main window, as they were in 0.9.4,
  before the Menus group. Their commands left the menus, so nothing is in two places, and their shortcuts work
  everywhere. File and Settings stay in the menus; the Edit menu, now empty, is gone.

### Bug fixes

- Fixes Fill amount being a chance, so fills came in different bars from one performance to the next.
- Fixes rhythm player performances sounding rigid, every note exactly on the grid.
- Fixes an acoustic drummer playing the ride or hi-hat between the hits of a crash it was riding.
- Fixes the Menus group's menus reading each item and its shortcut with no pause: there is a comma between them now.
- Fixes a half-open hi-hat that could, very rarely at fast tempos with the human feel, ring open: the foot that
  closes it could land a moment before it.
- Fixes exporting tracks on their own from a song with one track to a zip file saying "1 WAV files, one for each
  track".
- Fixes the Kit pieces list saying a piece was on when the groove gave it nothing to play.
- Fixes Latin jazz (jazz variation 4), which has no snare, still playing the style's soft snare ghost notes.

### Older projects

- Rhythm player regions made or changed since 0.9.4 place their fills on the steady count of bars, so a fill may come
  in a different bar than before.
- Those regions also play with the human feel, and an acoustic drummer riding the crash stops the ride and the hi-hat
  played by hand.
- In those regions, a kit piece the groove doesn't use is now off, unless a pattern or steps were made for it; a
  piece turned off by hand stays off.
- A drummer's hi-hat in those regions plays sixteenth notes above 140 beats a minute again.
- Rhythm player regions from before 0.9.4 that were never changed still play as they did: on the grid, with their old
  fills.

### New projects

- New rhythm player regions play with the human feel and with fills on a steady count of bars, and only the kit
  pieces their groove uses are on.

## 0.9.5 (21 October 2026, in testing)

### New features and improvements

- Every command now lives in the menus (File, Edit, Region, Track, Transport, Song, Keyboard, Options and Help),
  replacing the separate groups of buttons, for a cleaner and more consistent window. The Menus group's buttons
  still let Tab reach every menu.
- The Keyboard menu includes every musical keyboard setting as a submenu, with the current choice checked: Layout,
  Scale, Octave, Velocity, and the Arpeggiator's pattern, speed and octave range. The Keyboard controls area remains
  for quick changes while playing.
- Reforge picks each new performance at random from a near endless number, so fills, ghost notes, accents and
  voicings come out new every time.
- Reforge says only "Regenerated performance", including when several regions are reforged together.
- Undo and Redo step back and forth through each Reforge, one performance at a time.
- Each drum kit piece plays only its own sounds, in every kit and style; the hi-hat can no longer be moved onto the
  ride or crash.
- Above 120 beats a minute the ride plays eighth notes instead of runs of sixteenth notes, and sixteenth-note ride
  patterns leave its Pattern list.
- Above 140 beats a minute, a live drummer's hi-hat (rock, hard rock, metal, jazz, funk and pop) does the same.
  Drum machine styles keep their fast hi-hats.
- Export audio can fade out at the end of the song, over 5 to 30 seconds (10 to start). It is remembered, and
  tracks exported on their own all get the same fade, so they line up.
- When an export distorts, Musician Forge says where (bars and sections), by how many decibels, which tracks are
  loudest there, and the volume each would need.
- Audio exports say how far they have got, every 10 percent.

### Bug fixes

- Reforge now regenerates the way it was supposed to, instead of counting up through 9,999 numbered performances.
- Fixes a slight pop at the start of audio recordings when the microphone starts.
- Fixes an issue where the explanation in the Chord strips window was too wide for the window.
- Fixes a test that failed only on Windows (the program itself was not affected).
- The Linux testing setup now catches these Windows-only problems before a Windows test run.

### Older projects

- A closed hi-hat that played its rhythm on the ride, the ride bell or the crash plays on the hi-hat again.
- In rhythm player regions made or changed since 0.9.4, the ride plays eighth notes above 120 beats a minute, and a
  live drummer's hi-hat above 140. A sixteenth-note ride pattern already chosen stays, and says "eighth notes above
  120 beats a minute".
- Rhythm player regions from before 0.9.4 that were never changed keep playing as they did.
- Each rhythm player region keeps its performance, so it plays the same until it is reforged.

### New projects

- Everything above applies.

## 0.9.4 (9 October 2026, in testing)

### New features and improvements

- Export tracks on their own: every track you can hear, or only the tracks you choose, each as its own WAV file.
- MIDI export works with other programs: General MIDI instruments, a silent chord track, and the song's tempos, time
  signatures, keys and section markers. MIDI import reads all of these back.
- Rhythm players: Complexity sliders for each kit piece and part, Fill amount and Fill complexity for every player,
  Loudness sliders, softer drums, a Ghost note loudness slider, and more variety on Reforge.
- The hi-hat builds over the last two bars into a louder drummer region.
- Edit several rhythm player regions at once.
- Rhythm players play in every time signature, eighth swing plays in triplets, and Swing feel chooses eighth or
  sixteenth notes.
- Intensity now changes only how hard a player plays; Complexity changes how busy.
- A drummer plays with two hands: no more than two hand sounds at once in the live drummer styles.
- Your own chord strips (Control+Shift+J).
- Time signature changes keep each section's bars, and everything stays in its bar.
- New rhythm player region: P in the Regions list fills an empty part of a section.
- Quantize chooses the region you are on, the selected track or all tracks; Space selects notes in the event list;
  every key of a list inside a window also has a button.
- Nudge and trim regions from the keyboard.
- A project opens where you saved it; Enter opens a recent project; Browse projects; a shorter window title.
- The sound follows headphones plugged in or out.
- The crash-recovery copy is kept up to date a few seconds after every change.
- Duplicating a section puts the copy at the end of the song.
- A Menus group and a Settings group you can Tab to, and an Import file button.
- Go to start and rewinding stay in the section you are in.
- Remove Musician Forge, which never touches your projects.
- Only one Musician Forge runs at a time; windows bigger than the screen scroll; the rhythm player editor fits the
  screen.
- Musician Forge is free software under the MIT License.

### Bug fixes

- Fixes Kit pieces changes not being heard until some other change was made.
- Fixes Ghost note loudness other than 50 making the rhythm player windows say "Something went wrong".
- Fixes the event list moving your selection onto other notes, so Delete could remove notes you had not selected.
- Fixes half-open hi-hats ringing wide open with eighth-note swing.
- Fixes cymbals a kit lacks being silent: they now play on the nearest cymbal the kit has.
- Fixes Close project, then Yes, not always saving.
- Fixes Delete in selection mode deleting only the track you were on; regions now always ask first.
- Fixes a pop when the microphone starts.
- Fixes drum kits listed among other instrument families.
- Fixes Reforge on several regions playing the last region instead of the one in the editor.
- Fixes going silent without a word when switching to headphones failed.
- Fixes a half-made zip file left behind when a track export failed.
- Fixes the help naming Insert (screen readers keep it for themselves) instead of Alt+A.
- Fixes unsaved changes being lost when Windows shuts down or signs out.
- Fixes the distortion warning suggesting the master volume, which exports do not use.
- Fixes "(unsaved changes)" being read in the title every time a window closed.

### Older projects

- Rhythm player regions from earlier versions keep their sound (louder drums, fills only at the ends of phrases)
  until something in the region is changed, Reforge included; then they follow the new rules.
- Intensity now changes only how hard their players play, so they keep their grooves with slightly different details.
- Their rhythm players also play in the song's time signature instead of 4/4 cut short, eighth swing from 30 plays in
  triplets, and live drummers play with two hands.
- A kit piece's old complexity and loudness become the nearest Complexity and Loudness on the new 0 to 100 sliders.
- Each style keeps its own swing feel, so swing sounds as before.
- A cymbal the kit lacks, which was silent, now plays on the nearest cymbal the kit has.
- A song that chose one of the extra copies of a drum kit still plays it.
- They open at the start of the song until they are saved in this version; after that they open where they were
  saved.

### New projects

- New rhythm player regions play by the new rules: softer drums, fills set by Fill amount, a hi-hat build into a
  louder region, and more variety on Reforge.
- Each kit piece and part starts with Complexity and Loudness at 50, as the style plays it.
- Each style starts on its own swing feel.
- The chord strips play the key's chords until you change them.

## 0.9.3 (9 October 2026, in testing)

### New features and improvements

- Run Tests says how far it is and stops a test that is stuck, so the run goes on.
- Check Accessibility measures every window against the screen.
- The project window fits the screen and scrolls, and long notes in every window wrap.
- The public beta: the main branch for users, with the Guide for Testers; testers email Musician Forge's log.

### Bug fixes

- Fixes a take being lost when the window was closed, or a new project opened, while recording.
- Fixes Control+Z during a looping take also taking back the change made before the take.
- Fixes chord strips played legato cutting off shared notes.
- Fixes the event list and region windows changing the wrong note or region when opened during a take.
- Fixes a note struck again before it ended being cut short.
- Fixes an effect staying silent or noisy after something impossible was fed into it.
- Fixes pitch correction on a very short recording stopping later changes from being heard.
- Fixes quantize moving notes past the bar line with grids that do not divide the bar.
- Fixes windows closing on a mistyped number and losing what was typed.
- Fixes moving a tempo, time signature or key change to a beat its bar lacks deleting it.
- Fixes hand-made steps past the 64th being dropped in long bars.
- Fixes opening a damaged project's backup putting the wrong name in Recent projects.
- Fixes saving failing while OneDrive or an antivirus program held the file.
- Fixes settings from a newer version, or edited by hand, stopping Musician Forge from starting.
- Fixes errors nothing else caught being silent.
- Fixes stray asterisks in What's new being read as "star".
- Fixes the Windows voice speaking over itself without a screen reader.

### Older projects

- They open and play as before, with the bug fixes above.
- A project with damaged rhythm player settings plays them as an ordinary region instead of stopping the song.

### New projects

- Everything above applies.

## 0.9.2 (9 October 2026, in testing)

### New features and improvements

- Every rhythm player style has its own variations, each a different groove or part, described in words.
- Reforge keeps the variation and plays a new performance of the same groove.
- Kit pieces: every piece of the drum kit, and the part of the other players, has settings of its own: pattern,
  complexity, loudness and its own extras.
- Step pattern: an accessible step sequencer for any piece.
- A warning before changing the variation resets your hand-made steps.
- A rebuilt, heavier Forge Dubstep Kit.

### Bug fixes

- Fixes a song made only of rhythm players saying there was nothing to export.
- Fixes a damaged project file leaving a project stuck.
- Fixes the Step pattern not starting from what is heard, and editing a part's step changing the whole part.

### Older projects

- Rhythm player regions open on variation 1, which is each style as it was, and keep their old variation number as
  their performance, so they sound exactly the same.
- A project that uses the Forge Dubstep Kit plays the rebuilt kit.

### New projects

- They are saved in a newer file format, so they open in 0.9.2 and later.
- A new rhythm player region starts on variation 1 of its style.

## 0.9.1 (9 October 2026, in testing)

### New features and improvements

- F6 and Shift+F6 jump from area to area in the project window.
- The track and region you are on end with "selected" in their lists.
- Import audio files of every common kind (WAV, MP3, M4A, AAC, FLAC, Ogg, Opus, AIFF, Apple Lossless, Windows Media
  Audio), and MIDI files.
- Low-latency hearing yourself (Windows 10 and later).
- Raw microphone sound, without Windows' noise reduction.
- The measured recording delay is remembered for each output and microphone.
- Clearer pitch correction.

### Bug fixes

- Fixes a take seeming lost when recording past the end of a looping section.
- Fixes hearing yourself staying behind after a hiccup.
- Fixes Run Tests' guitar pack stage printing a harmless warning.

### Older projects

- They open and play exactly as before.

### New projects

- Everything above applies.

## 0.9.0 (8 October 2026, in testing)

### New features and improvements

- The program is now called Musician Forge (it was Melody Forge); your songs and settings move with it.
- Automation: volume, pan and effect settings can change over time, and Write automation records them as the song
  plays.
- A project can have up to 100 tracks.
- Run Tests checks the sound engine step by step, and runs each test file on its own.
- Every menu item has its own underlined letter.

### Bug fixes

- Fixes Musician Forge closing on Windows as soon as it played: Install or Update now installs FluidSynth 2.5.7,
  and Musician Forge refuses the builds that crash.
- Fixes changing a track's volume, pan or effects while playing cutting off notes.
- Fixes a stutter when a guitar pack was chosen while the song played.
- Fixes swing leaving the notes between the swung ones in place, which roughened drum fills.
- Fixes Region settings trimming a region that was not changed.
- Fixes Install or Update showing an old report when its self check was ended by Windows.
- Fixes Run Tests' guitar pack stage staying silent until it ended.

### Older projects

- The first Install or Update moves the Melody Forge Songs and MelodyForge folders, with everything in them, to their
  new names, and keeps the recent projects list.
- Project files still end in .mforge, so every project opens as before.
- Swung rhythm player regions now move the notes between the swung ones too, so their fills sound cleaner.

### New projects

- They are saved in a newer file format, so they open in 0.9.0 and later.
- They can have up to 100 tracks.

## 0.8.0 (8 October 2026, in testing)

### New features and improvements

- Five rhythm players: Anvil (drums), Bellows (bass), Ember (keys), Spark (synth) and Hammer (guitar).
- Eleven drummer styles, and two new kits of Musician Forge's own: Forge House and Forge Trap.
- A rhythm player editor: style, patch, intensity, complexity, fills, swing and Follow.
- Reforge, Follow (lock to another track, even a recording) and Turn into notes.
- The chord track: the song's chords, which rhythm players play.
- Two distorted electric guitar packs.
- Trim and loop regions (Region settings).

### Bug fixes

- No bug fixes in this version.

### Older projects

- They open and play as before, with an empty chord track.

### New projects

- Everything above applies.

## 0.7.0 (8 October 2026, in testing)

### New features and improvements

- Effects on every track: EQ, compressor, distortion (with a bit crusher), delay and reverb, plus pitch correction
  on audio tracks, with 36 presets.
- Measure the recording delay, so recordings land on the beat.
- Separate timing adjustments for the musical keyboard and the microphone.
- Each track's sound is processed on its own.

### Bug fixes

- No bug fixes in this version.

### Older projects

- They open with no effects on their tracks, and their volume and pan sound the same as before.

### New projects

- Everything above applies.

## 0.6.0 (7 October 2026, in testing)

### New features and improvements

- Regions on every track, listed after Tracks, with cut, copy, paste, duplicate, split, join, mute, rename and
  move.
- Selection mode (Shift+F8): cut, copy, paste, duplicate, delete, mute and solo work on everything selected.
- Whole tracks can be cut, copied, pasted and duplicated.
- The help recommends wired headphones.

### Bug fixes

- No bug fixes in this version.

### Older projects

- Each track gets one region for each section that has notes.

### New projects

- Recording makes a region that covers exactly what was recorded.

## 0.5.1 (7 October 2026, in testing)

### New features and improvements

- M4A export (AAC), about a tenth of the size of WAV, good for sharing and Apple devices.
- The install self check tests M4A export.

### Bug fixes

- No bug fixes in this version.

### Older projects

- They open and play exactly as before.

### New projects

- Everything above applies.

## 0.5.0 (7 October 2026, in testing)

### New features and improvements

- Audio tracks: record your voice or any instrument, with takes, punch-in and a recordings list.
- Import WAV files.
- Choose and test the microphone in Audio settings.
- A folder for each project, with its recordings and exports.
- Musician Forge's own Save project as and Open project windows.
- Let the sound ring out after the end of an export.
- Move up and Move down buttons for tracks.

### Bug fixes

- Fixes the keyboard controls' labels being shifted by one, so screen readers named the boxes wrongly.

### Older projects

- A project saved as a file on its own keeps working where it is; its recordings and exports go into Recordings and
  Exports folders beside it.

### New projects

- Each project is saved in a folder of its own, with a Recordings folder and an Exports folder.

## 0.4.0 (7 October 2026, in testing)

### New features and improvements

- The Forge Dubstep Kit: drum sounds made inside Musician Forge, with no outside samples.
- The Forge 808 Sub bass.
- The drum layout speaks the kit's own sound names.

### Bug fixes

- No bug fixes in this version.

### Older projects

- They open and play exactly as before.

### New projects

- Everything above applies.

## 0.3.0 (7 October 2026, in testing)

### New features and improvements

- A start screen to choose a project, and Close project.
- Show keyboard controls: layout, scale, octave, velocity and the arpeggiator, all reachable with Tab.
- The Chord strips layout and a scale choice for the keyboard.
- The arpeggiator.
- An Edit group and a Help group.

### Bug fixes

- Fixes R and Enter starting a recording or jumping to the start while typing in a list or box.
- Fixes key names that did not match their key signatures (E flat minor showed 6 sharps).
- Fixes deleted or moved projects staying in Recent projects.

### Older projects

- They open and play exactly as before.

### New projects

- Everything above applies.

## 0.2.1 (7 October 2026)

### New features and improvements

- After every save or export, Musician Forge says which folder it went into.
- Every save, open, export and recovery is written to the log.

### Bug fixes

- Fixes an export going into the wrong folder: Save As and exports always start in the project's folder or in
  Musician Forge Songs.
- Fixes the tests creating folders in the real Documents folder.

### Older projects

- They open and play exactly as before.

### New projects

- Everything above applies.

## 0.2 (7 October 2026)

### New features and improvements

- Buttons in named groups.
- Song sections that loop, with All sections to play the whole song, and recording that layers each pass.
- Rewind and Forward say when you reach a section's edge.
- Quiet recording: nothing is spoken when recording or playback starts.

### Bug fixes

- No bug fixes in this version.

### Older projects

- A song from 0.1 opens as one section, long enough for all its notes.

### New projects

- A new project starts as one 8-bar section.

## 0.1 (7 October 2026)

### New features and improvements

- The first working version: musical typing on the computer keyboard (piano, scale and drum layouts), FluidSynth
  with GeneralUser GS, tempo, time signature and key changes, the event list, quantize, WAV and MIDI export,
  autosave and crash recovery, and support for NVDA, JAWS and Narrator.

### Bug fixes

- None: the first version.

### Older projects

- None: this is the first version.

### New projects

- Everything above applies.
