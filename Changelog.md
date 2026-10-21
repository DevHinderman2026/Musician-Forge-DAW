# Musician Forge release notes

Every version of Musician Forge, newest first, from the first working version on, so you can follow how it was
developed. Each version starts with its release notes: new features and improvements, then bug fixes. The details
of each version follow. Dates are when the version reached Russell's laptop.

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

### In detail

Still a public beta, in testing. What Russell asked for after trying it: immediate bug fixes and feature
improvements, then important bug fixes and improvements from his Windows test run.

**Important bug fixes and improvements (21 October, 3:30 AM),** from Run Tests on Windows (2 problems; Check Accessibility found none):
- **The Chord strips window's note fits the window again.** Its explanation (which chords the strips hold) was one
  line 721 pixels wide, wider than the window should be. Windows did not re-wrap it after the words changed; it is
  now wrapped by Musician Forge itself.
- **A window test that read a menu after it had closed** was fixed (the program was fine; only the test failed on
  Windows). The Linux stand-in the tests also run on now refuses both of these, as Windows does, so they are caught
  before a Windows run.

- **Fade out at the end of exports.** Export audio has "Fade out at the end of the song" next to the ring-out,
  with a slider from 5 to 30 seconds (10 to start), remembered for next time. The fade ends exactly where the song
  ends and gets softer evenly to the ear (halfway through it is 12 dB down), so the ring-out is dimmed while it is
  on. WAV, M4A and tracks on their own (each with the same fade, so they line up). It is heard in the exported file,
  not while playing.
- **The distortion warning says where, how much, and what to turn down.** Instead of "certain parts of the song":
  the bars and sections where it distorts (the first three places, and how many more), how many decibels too loud
  it gets, the loudest tracks there and the volume each would need ("Drums from volume 80 to 67"). To find them,
  an export that distorts plays each track on its own up to the last place it distorts (at half the sample rate,
  to be quicker). Tracks exported on their own name each track whose file distorts. The level is measured before
  full scale cuts the sound off, so the decibels are real.
- **Exports say how far they have got**, every 10 percent up to 100, and say when they move on to finding the
  loud tracks.
- **A softer start for the microphone.** A slight pop was still there when recording audio: its first 80 ms are now
  silent (was 60) and it fades in over a rounded 25 ms (was a straight 15 ms); hearing yourself fades in over
  20 ms (was 10).

- **Every command is in the menus.** The groups of buttons (Transport, Track, Edit, Region, Song, File and
  Settings) are gone, to reduce clutter: each did what an item of its menu does, and every one of those items is
  in its menu (File, Edit, Region, Track, Transport, Song, Keyboard, Options). The Menus group stays, so Tab
  still reaches every command: its buttons open the menus, and Alt opens the menu bar. F6 now goes Tracks,
  Regions, the Musical keyboard, the Keyboard controls, the Menus group and Status.
- **The Keyboard menu has every keyboard setting.** Layout, Scale, Octave, Velocity, and the Arpeggiator's
  pattern, speed and octave range are submenus, the current choice checked; choosing one says it. The Keyboard
  controls area stays as well (Russell's choice), for trying settings quickly while playing.
- **Reforge now regenerates the way it was supposed to: at random, from a near endless number of performances.**
  It used to count up, one performance
  at a time, to 9,999. Now each Reforge picks one at random from about nine quadrillion, so the fills (where they
  come and their shapes), the ghost notes, the accents and the voicings come out new every time. It says only
  "Regenerated performance", also when several regions are reforged together. Control+Z still goes back.
- **Each kit piece plays only its own sounds.** The Closed hi-hat no longer has "Play this rhythm on" (the ride,
  its bell or the crash): the hi-hat plays on the hi-hat, in every kit and style. Its variations, patterns,
  openness and the rest are still there, and the Ride still chooses between its own sounds (the ride, its bell, the
  second ride). A project that had moved the hi-hat to a cymbal plays it on the hi-hat again.
- **No sixteenth-note runs on the ride in fast songs.** Above 120 beats a minute the ride keeps its eighth notes
  and leaves out the sixteenths between them, whatever made them (the style, a pattern, Complexity), and the
  Pattern list leaves out ride patterns in sixteenths there (a pattern already chosen stays and says "eighth notes
  above 120 beats a minute"). The same for a drummer's hi-hat (rock, hard rock, metal, jazz, funk, pop) above 140,
  where two hands could still share sixteenths. Drum machines (dubstep, house, trap) keep their fast hi-hats, a
  single hit between the eighths (jazz's dotted-eighth bell) stays, steps set by hand stay, and a tempo change
  part way through a region counts from the bar it starts in. Regions from before 10 October that were never
  changed keep playing as they did until you change them.

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

### In detail

What Russell found trying 0.9.3, and one thing he asked for.

**The final review (10 October, evening).** One more pass over the whole program before the beta, with new tests
that open every window and make thousands of random changes. What it found, all fixed:

- **A Kit pieces change is heard straight away again.** Since that afternoon, a change to one region's piece (the
  kick turned off, a loudness, a pattern, the hi-hat's openness) was only heard after some other change.
- **Ghost note loudness** at anything but 50 made the rhythm player editor and the piece's window say "Something
  went wrong" every time they showed that region.
- **The event list keeps your selection on the notes you selected.** Adding a note, or giving one a new time, could
  move the selection onto other notes, so Delete removed notes you had not selected. Quantizing the whole track or
  all tracks now clears the selection, as quantizing the selected notes already did.
- **Half-open hi-hats with eighth-note swing** (Swing 30 or more): the foot no longer closes the hi-hat at the very
  moment it is struck on the "and", which made those hits ring wide open. The same in hi-hat builds.
- **A cymbal the kit lacks is described as it is heard**: "not in this kit, so the crash cymbal plays it", no longer
  "silent", since Musician Forge plays it on the nearest cymbal the kit has.
- **Alt+A instead of Insert** in the help and in empty lists (events, effects, automation, chord track, sections):
  NVDA and JAWS keep Insert for themselves. Alt+A presses the window's Add button; Insert still works.
- **Several rhythm player regions edited together**: Reforge plays the region in the editor (the last region of
  the selection used to take over), and a change some of them cannot take (another variation, on a region with
  hand-made steps) is said: "1 of the 3 regions could not take that and stayed as it was".
- **Headphones**: if Windows' sound system cannot be started again when the output changes, Musician Forge says so
  instead of going silent without a word.
- **Tracks on their own, in a zip file**: if writing the zip fails (a full disk, say), no half-made file is left
  in the folder.
- **A button for every key of a list** (Russell's choice): the event list (select or unselect, select all, play,
  a semitone or an octave up or down), the Step pattern (turn the step on or off, previous and next sound, louder,
  softer) and Export audio's Tracks to export (select or unselect the track, select all tracks) have a button for
  each key, right under the list, so Tab reaches everything. The keys still work.

- **Tracks on their own.** With WAV chosen, Export audio offers the whole song, every track you can hear, or
  only the tracks you choose (Space selects; the vocals alone, say). One track is one WAV file, several a zip
  file; every file has the song's length, so they line up.
- **MIDI export, fixed for other programs**: still one file. Each track names its General MIDI instrument, so
  the guitar packs come out as a Distortion Guitar (another program played them as a piano) and acoustic kits as the
  Standard kit (an electronic kit played instead). The chord track is a silent track of its own, each chord
  named. No note plays after the music ends (a chord at the very end used to sound on its own). The first
  track holds only the tempos, signatures, keys and section markers, so no empty extra track appears. It says
  when it is done.
- **A kit piece's Complexity works.** It is now a slider from 0 to 100 (50 as the style plays it): higher adds
  in-between eighths, then some sixteenths, never more than a drummer could play; lower thins it to the beats. It
  did nothing before on most pieces. The part of the bass, keys, synth and guitar has it too, and Loudness is a
  slider. Older projects' piece settings turn into the same Complexity.
- **Fill amount and Fill complexity.** Fill amount 0 is no fills and 100 a fill in every bar; Fill complexity sets
  how big each fill is (a pickup up to a whole bar for the drummer, up to half a bar for the others). A simple
  pad has no fills.
- **Softer drums.** Intensity 100 is now about as loud as 40 was; the rim click comes at 20 or below, and ghost
  notes follow the kit's loudness. The snare has a Ghost note loudness slider.
- **More variety on Reforge**: new fill shapes and each performance's own accents and extra kicks; the bass now
  and then jumps an octave.
- **Hi-hat builds into a louder region.** When the next drummer region on the track is at least 20 Intensity
  louder (50 going to 100, say), the hi-hat builds over the last two bars: closed, then half open, then wide open
  into the crash. Only then: ordinary fills don't build, and at Intensity 100 there are no builds (nothing to build to).
- **Older regions keep their sound.** Rhythm player regions made before these changes play exactly as they did
  until you change something in that region (Reforge included); then they follow the new rules.
- **Edit several rhythm player regions at once**: select them, then Open region; every change goes to all of
  them as one undo step.
- **No silent cymbals.** A drum sound the chosen kit has no sample for plays on the nearest one it has (a
  splash or china on the crash, a second ride or ride bell on the ride, a missing tom on the next tom): the
  Forge House and Forge Trap kits have no splash or china. MIDI export writes the splash and china as the crash
  and the second ride as the ride, since other programs' kits often lack them (a splash was silent in one).
- **The distortion warning after an audio export** now says there may be distortion in certain parts, and that
  reducing track volumes will help. It no longer suggests the master volume, which exports do not use.
- **MIDI import, the same rules in reverse**: Distortion Guitar becomes the guitar pack, kit numbers choose the
  matching kit, a "Chord track" becomes the chord track, and another program's empty time after the last note
  does not become bars. Musician Forge's own files come back with their exact instruments.
- **Quantize chooses what to tidy.** Control+Q offers the region you are on, the selected track or all tracks.
- **Space selects notes in the event list.** Space selects or unselects the note you are on, Control+A selects
  them all, and P plays them. Delete, moving and quantizing work on the selected notes.
- **Headphones: the sound follows Windows.** Plug headphones in or take them out, and within a second Musician
  Forge plays where Windows does and says "Sound now on" and the output's name. While recording it waits until
  you stop. This is with Audio settings on Windows default (as they start); an output chosen there by name stays
  chosen.
- **Close project, then Yes, saves.** Musician Forge now reads every save straight back and says so if the file
  does not hold the project; it also notices a change that somehow missed the undo list, so closing always asks
  when the project has anything unsaved. The question and your answer go into the log.
- **No more "(unsaved changes)" in the title.** Screen readers read it every time a window closed. Instead,
  Musician Forge keeps its crash-recovery copy up to date a few seconds after every change (it used to be every
  two minutes), in its own folder, never the project's. If Musician Forge stops suddenly, the next start offers
  that copy. Saving the project retires the copy, so an older one is never offered over a newer save.
- **Duplicate puts the copy at the end of the song.** With sections 1, 2 and 3, duplicating any of them makes
  section 4 (it used to go straight after the section it came from).
- **Your own chord strips** (Russell: make the chord strips customizable). Control+Shift+J, the Customize chord
  strips button in the keyboard controls or the Keyboard menu: the eight strips (A to K) in a list; Enter changes
  one (root, chord type, a different bass note), Space plays it, Use the key's chords goes back. Saved with the
  project, kept through key changes, the bass keys 1 to 8 follow, one undo step each.
- **Time signature changes keep the bars** (Russell: an 8-bar section went to 11 bars in 3/4). Every section keeps its
  number of bars, and notes, regions, recordings, chord changes and automation stay in their bar on the same beat;
  rhythm player regions keep their bars and play in the new meter. A note on a beat that shorter bars no longer
  have is left out (Musician Forge says how many; Control+Z brings them back).
- **Enter opens a recent project** on the start screen (and a double-click), saying "Opening" and its name at
  once, and Open project there is now **Browse projects**.
- **A shorter window title**: "My Song - Musician Forge", without .mforge.
- **Rhythm players in every time signature** (Russell: "If I switch the time signature the drummer should play in 3/4
  time. Same with all the other session players"). Each bar is felt in its own beats: three in 3/4, two dotted
  beats in 6/8 (four in 12/8), 2+2+3 eighths in 7/8, five in 5/4; every style plays from its groove beat by beat
  (beat one, the backbeat, the middle, the last beat leading on). A rock drummer in 3/4 plays the kick on one and
  the snare on two and three, in 6/8 the snare on the second big beat with eighths on the hi-hat; the bass and keys
  change on beat three in 3/4 instead of the and of two, a walking bass walks three beats in 3/4 and two in 6/8.
  4/4 plays exactly as before. They used to play 4/4 cut off or wrapped round.
- **Eighth swing in triplets** (Russell: with eighth swing the drummer's fills were "a little rough"). From a Swing
  of 30, sixteenths are played in threes, as in a shuffle: one, the middle triplet and the swung and (the "a" of
  the beat joins the and). Fills roll in even triplets, and every player locks to the same feel. Eighth swing is
  left out of the dotted beats of 6/8, 9/8 and 12/8, which are in threes already. Sixteenth swing is unchanged.
- **Loudness of a kit piece or part in percent** (Russell: 40 was not loud enough). 0 to 100: 50 is as the style plays it,
  100 twice as hard (as loud as a note can be), 0 silent. Songs that used the old setting get the nearest level.
- **Follow, the track to follow and Reforge** no longer read the whole region summary: the lists say their own item,
  Reforge says "New performance of variation 2 of 6".
- **A project opens where you saved it.** Saving keeps the playhead and the track you were on, and opening goes back
  there and says where ("Section 3, Bar 19, beat 3"); it used to open at the start of section 1. Moving the
  playhead is never an unsaved change, and older copies of Musician Forge still open the file. The crash-recovery
  copy keeps the place too.
- **New rhythm player region** (Russell: a new section has no region, and there was no way to add one on a rhythm
  player's track). P in the Regions list, the New rhythm player region button in the Region group, or the
  Region menu: a region at the playhead that fills the empty part of its section, with the same player and style
  starting from the style's own settings and first variation. Control+Z takes it back.
- **A drummer with two hands.** In rock, hard rock, metal, jazz, funk and pop, no more than two hand sounds start
  together, and a crash takes the hi-hat's or ride's place on its beat (a drummer does not play a hi-hat, a crash
  and the snare at once). The Step pattern view shows the same. Steps you set by hand are kept; the electronic
  styles still stack sounds like drum machines.
- **Quieter pattern and variation changes.** A kit piece's Pattern list says only which pattern ("Variation 3's"),
  with what it plays in This piece now; changing a pattern, a choice or a check box in a piece's settings adds no
  announcement of its own; Previous and Next variation say "Variation 3 of 6"; turning a piece on or off says
  "Kick off".
- **Remove Musician Forge.** A new file next to Install or Update Musician Forge. It asks first, then removes what
  the installer put on the computer (Musician Forge's Python environment, sound engine and sounds, in
  %LOCALAPPDATA%\MusicianForge), and asks whether to keep your settings for a reinstall. Your projects in
  Documents, Musician Forge Songs, are never touched, and open again after a reinstall (still .mforge). It warns
  you about a crash-recovery copy of unsaved work, and says so if Musician Forge is still open.
- **A Menus group:** a button for each menu (File, Edit, Region, Track, Transport, Song, Keyboard, Options and
  Help), so Tab reaches every menu item. Each opens the menu under the button with the same items, shortcuts and
  check marks as the menu bar, which still opens with Alt. It takes the place of the Help group.
- **Go to start and rewinding stay in the section.** With All sections off, Enter (Go to start) goes to the start of
  the section you are in, and Rewind (comma) and Shift+comma stop there and say "Start of" the section. With All
  sections on they go back through the whole song, as before. Previous section still leaves the section.
- **A Settings group you can Tab to:** Audio settings, Measure the recording delay (opens Audio settings on the
  measurement) and Preferences, before the Help group; F6 reaches it too. Shortcuts: Control+Shift+O for Audio
  settings, Control+Shift+D for the measurement. Until now these were only in the Options menu.
- **No pop when the microphone starts.** The first 60 milliseconds after the microphone opens are kept silent and
  it fades in over 15 milliseconds, for the take and for hearing yourself (both the usual way and low-latency);
  hearing yourself also fades in over 10 milliseconds whenever it switches on. Timing is unchanged.
- **Drum kits only in Drum Kits.** GeneralUser GS has a second copy of its 13 kits on another bank, which were
  listed among the Piano, Organ, Guitar, Bass, Strings and other instruments. The copies are no longer listed (the
  same kits are in Drum Kits, where they play as drum kits); a song that chose a copy still plays it.
- **Intensity is how hard, Complexity is how busy** (Russell: intensity "is just supposed to change the velocity").
  For every player, moving Intensity never adds or takes away notes: it plays the same notes softer or harder.
  Complexity alone makes a part busier (more hi-hats, ghost notes, a bass in half notes instead of whole notes,
  keys and synth arpeggios in sixteenths, guitar chugs and strums). The drummer also changes how it plays:
  below 35 the snare goes to the rim (a cross-stick); from 70 the hi-hat is half open, from 85 open. The
  snare's Rim click (by intensity, always, never) and the hi-hat's How open (by intensity, closed, half open,
  open) can fix either. Older songs follow the new rules too, so their players keep their grooves with slightly
  different details.
- **More cymbal choices for the drummer.** The Closed hi-hat piece has Play this rhythm on: the hi-hat, the ride,
  the ride bell or the crash (move the beat to the ride for a chorus). The Ride has Which ride: the ride, the
  ride bell or the second ride. New patterns: the ride in sixteenth notes, a crash wash in eighth notes, and
  disco sixteenths on the hi-hat (open on the and of each beat). These stay through any variation.
- **Swing feel: eighth notes or sixteenth notes.** Every rhythm player's editor has a Swing feel choice right
  after the Swing slider. Eighth notes swings the "and" of each beat; sixteenth notes swings the "e" and the
  "a". Each style starts on its own feel, so songs made before sound exactly the same; a new style starts on
  its own feel again. Control+Z undoes it.
- **Delete asks about everything you selected.** In selection mode, Delete in the Tracks list (and the Delete
  track button and menu item) deleted only the track you were on and asked only about that one; now it asks
  "Delete 3 tracks and everything on them?" and deletes them all. Delete in the Regions list used to delete
  the region, or every selected region, without asking; now it always asks first ("Delete region 2, Riff?"
  or "Delete 4 regions?"). Control+Z still brings them back.
- **An Import file button** in the File group (Import was only in the File menu, Control+Shift+I).
- **Nudging and trimming regions from the keyboard** (Russell asked how to trim and nudge regions, and how to
  make a rhythm player's region longer). In the Regions list: Alt+Left and Alt+Right move the region (or the
  selected regions) by the nudge step; left and right bracket move its start; Shift+left and Shift+right bracket
  (or Alt+Shift+Left and Alt+Shift+Right) move its end, which is how a rhythm player's region gets longer (the
  player fills the new bars). N changes the nudge step: 1 bar, a quarter note, an eighth note or a sixteenth note
  (Shift+N goes back), and it is remembered. Each key says where the region now starts or ends and how long it
  is; a region never moves over another one (Musician Forge says what is in the way, without a window to close);
  a recording's edges stop where the recording does; trimming notes away says how many (Control+Z brings them
  back); presses of the same key in a row undo together. The Region menu has the same commands. Region settings
  (Alt+Enter) and Move region still take typed positions.
- **The rhythm player editor fits the screen.** Its settings scroll and its buttons stay in sight below them;
  the drummer's editor was taller than the screen, so its note was out of sight (found by Check Accessibility).
- **Musician Forge is free software under the MIT License** (the LICENSE file).
- **Windows bigger than the screen scroll.** On a smaller screen, or with Windows' scaling above 150 percent, a
  window such as Audio settings could be taller than the screen; now it gets scroll bars instead of controls out
  of sight. Where everything fits, as on Russell's laptop, nothing changes.
- **Only one Musician Forge at a time.** Starting it again while it is open says "Musician Forge is already
  open. Use Alt+Tab to go to it." (Russell's log showed it started twice, five seconds apart: two copies share the
  settings and the crash-recovery copy, so one could spoil the other's.)
- **Windows shutting down or signing out** with unsaved changes no longer loses them: the next start offers to
  recover the project, as after a crash (it used to count as closed properly).
- Crash recovery itself is unchanged: after a crash the next start asks "Musician Forge did not close properly
  last time. Recover the project you were working on?", and Yes brings the project back with its own name and
  folder. A test now runs the whole path, Yes and No.

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

### In detail

A review of the whole program, line by line, after the 9 October Windows test run. Every bug it found is fixed,
each with a test.

**Recording**
- **Closing the window while recording asks to save the take.** With Alt+F4 or Exit during a take, the take was
  lost without a question when nothing else had changed.
- **New project or Open project while recording asks about the take first.** The take used to arrive after the
  new project was made, and went into its first track.
- **Control+Z during a looping take** takes back that pass only: the passes after it are an undo step of their
  own (the next Control+Z also took back the change made before the take). A take whose Automatic section
  Control+Z took away is kept instead of lost.
- **Chord strips played legato** no longer cut off notes the next chord shares.
- Closing Audio settings during the microphone test no longer swallows the start of a recording made straight
  after it.
- Measure the recording delay names the Microphone timing adjustment, as Audio settings does.
- **The Event list and the region windows wait until the take is over.** Opened during a take, they pointed at
  notes and regions by their place in the list while the take added notes under them, so Delete or OK could
  change the wrong one. Now Control+L, and Enter, Alt+Enter, F2 or Move region in the Regions list, say "Stop
  recording before..." and open nothing (Russell's choice, 9 October).

**Playing and exporting**
- **A note struck again before it ended** no longer cuts the new note short, when playing and in exported MIDI
  files: the first one ends where the second starts, as the synthesizer plays it.
- **A broken number in an effect** (a reverb or delay fed something impossible) is silenced at once, and the
  effect starts clean, instead of staying silent or noisy for good.
- **Pitch correction on a very short recording** (under a hundredth of a second) no longer stops every later
  change from being heard; a recording that cannot be corrected plays as recorded.
- Quantize with a grid that does not divide the bar (half notes in 7/8) no longer moves notes past the bar line.
- An export whose instruments cannot start no longer leaves a half-made file in the Exports folder.

**Editing**
- **Windows that closed on a mistyped number stay open** with everything you typed and say what is wrong: Go to
  bar, Move region, Quantize, Section settings, Recording settings, Region settings, New rhythm player, Track
  settings, Audio settings, the chord track's windows, automation points and effect settings. Audio settings had
  already changed some settings before it found the mistake.
- **Moving a tempo, time signature or key change** to a beat its bar does not have leaves it where it was (it was
  deleted, and trying again deleted the next one). A move is now one undo step.
- **Beats past 16** (in bars such as 21/16) can be typed in the chord, region and automation windows.
- **Hand-made steps in long bars:** in a bar of more than 16 beats (32/4 has 128 steps) a step past the 64th was
  dropped without a word, and so were the style's own hits there once any step was changed.
- Spoken positions never say "beat 5" of a 4-beat bar just before a bar line.
- The Edit menu had a doubled separator.

**Projects and settings**
- **Opening a damaged project's backup** keeps the project's own name in Recent projects (not "Song.mforge.bak")
  and says "Opened the backup of"; saving never puts the damaged file in place of the good backup.
- Saving waits a moment for a file that OneDrive or an antivirus program is holding, instead of failing.
- Damaged project files (and a picture renamed to .mforge) are refused in words; damaged rhythm player settings
  play as an ordinary region instead of stopping the song.
- Settings from a newer version, or edited by hand (also saved by Notepad), never stop Musician Forge from
  starting: anything it does not know goes back to its default.
- Project names Windows keeps for itself (CON, NUL and the like) are saved safely.
- If checking for a project to recover goes wrong, the start screen still opens.

**Screen readers and windows**
- **An error nothing else caught is said:** "Something went wrong. The details were saved in the logs folder"
  (pressing the button seemed to do nothing).
- What's new had stray asterisks that screen readers read as "star".
- **The project window fits the screen and scrolls** (it was taller than a laptop screen at 125 or 150 percent
  scaling), and long notes in every window wrap.
- Without a screen reader, the Windows voice no longer speaks over itself.
- The rhythm player windows close the way Windows requires (the one test problem in the 9 October run).

**Where things are on GitHub**
- **main**, the branch people download, has the program, Install or Update Musician Forge, Start Musician
  Forge, the Read Me, Changelog and Credits, and the Guide for Testers: the beta is public (Russell, 9 October).
  The tests and the testing tools (Run Tests, Check Accessibility and Diagnose) are on the **development**
  branch, which the Musician Forge folder on Russell's laptop works from. tools\make_main.py makes each release
  on main from it.
- Testers send what they found by email, with Musician Forge's own log: the Guide for Testers says how.
- Check Accessibility now also measures every window against the screen (too big, partly off it, controls out of
  sight) and checks every control of a window, not only the first 20.
- **Run Tests says how far the tests are**, each 10 percent ("Tests 30 percent done", also in the window's title),
  and a test that takes more than two minutes is stopped and named, so the run goes on. On 9 October a check
  inside a window test failed on Windows, became a real message box, and the run waited behind it with the error
  sound: window tests can no longer open a message box that waits, and that check now measures in pixels.
- Test runs and Check Accessibility remove their own temporary folders; Install or Update keeps retrying a
  download that an antivirus program is checking; Diagnose reads a settings file saved by Notepad.

Tested in Claude's workspace and the laptop's Linux shell: all 831 tests (the 118 window tests with a stand-in for
wxPython), each fix with a test that fails on 0.9.2 where that could be shown. Not yet run on Windows.

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

### In detail

**Rhythm players: real variations, and a Reforge that keeps them**
- **Every style has its own variations**, at least four (Anvil's dubstep and rock have six), each a different
  groove or part, worked out from how each kind of music is played and described in words: "Variation 2 of 6:
  kick on one and the and of two, hi-hats in eighths". In the editor, Variation chooses one, and Previous
  variation (Alt+V) and Next variation (Alt+X) step through them. The Regions list says "variation 2 of 6".
- **Reforge keeps the variation** (Russell, 8 October: "super important"): it plays a new performance of the
  same groove, with new fills and small details, says "New performance of variation 2 of 6" and plays the
  region; Control+Z goes back to the one before. Changing the style starts again at variation 1 if the new
  style has fewer, and says so.
- **Older projects sound exactly the same**: they open on variation 1, which is each style as it was, with
  their old variation number kept as the performance (checked note for note on 1,620 cases). Projects are
  saved as file version 8.

**Rhythm players: every piece of every player**
- **Kit pieces** in Anvil's editor: kick, snare, clap or rim, closed hi-hat, open hi-hat, toms, crash cymbals,
  ride, congas and bongos, and shaker, tambourine, cowbell and claves. Each line says what the piece does
  ("Crash cymbals: on, every 4 bars, crash cymbal"); Space turns a piece on or off, Enter opens its settings.
  Bellows, Ember, Spark and Hammer have one piece, the part. The summary (Alt+S) lists the pieces that are
  off, hand-made or changed.
- **A piece's settings**: Pattern (the variation's own, another variation's, none, or a common one; a part
  can borrow any variation of any of its player's styles), complexity and loudness for that piece alone, and
  its extras: half or double time for the kick and the snare; ghost notes (as the style plays them, none, or
  more) and a rim click for the snare; closed, half open or open hi-hats, and open on the offbeats; the toms in
  fills or not; when a crash comes (where the region starts and after fills, at each section, every 2, 4 or 8
  bars, on the followed track's strongest hits, or never) and which cymbal; the ride's bell on the beats. A
  part: the chord track on or off, an octave up or down, short, normal or long notes, the root only, and
  passing notes into each chord change. Only sounds the kit has are offered, and a piece the kit lacks says
  so ("Congas and bongos: on, not in this kit").
- **Step pattern**, our own accessible step sequencer: every step of one to four bars, one per line ("Bar 1,
  step 3, the and of one: on, kick, loudness 90"); Space turns a step on or off, Left and Right choose its
  sound, Page Up and Page Down its loudness; Copy, Paste and Clear, Control+C and Control+V. It starts from
  exactly what the piece plays in the region's first bars, so changing one step changes only that step: a drum
  step keeps every sound on it (a conga and a bongo together), and a part's steps start as "as the style plays
  it", which plays the style's own notes on that step. Changing a step makes the piece hand-made: the pattern
  repeats through the region, Reforge keeps it, and what comes by itself stays on top (crashes where the region
  starts and after fills, kicks on chord changes and on a followed track, a trap hi-hat roll). Settings a
  hand-made piece no longer uses are dimmed, and its settings window says why.
- **The warning** (Russell, 8 October): changing the variation resets hand-made steps, so Musician Forge first
  says so in words, "Changing to variation 3 resets your hand-made steps on Kick and Snare. Change the
  variation?", with Change and Cancel (Escape and Enter cancel). Control+Z brings back the old variation and the
  steps together. Reforge never resets them.

**A more dubstep Forge Dubstep Kit** (Russell, 8 October: bigger, heavier snare; deeper, punchier kick; grittier)
- Rebuilt from research into how dubstep drums are made: a kick whose sine drops from about 235 Hz to about 50 Hz
  within 100 ms, driven hard while it holds for 60 ms and then cut off to leave room for the bass; a snare with a
  thick body near 190 Hz, a bright snap, a short crack, a clap layer and a room that rings for a second; claps, a
  clap snare and hats with grit added beside them (parallel distortion and a bit crusher); a deeper 808 kick whose
  overtones carry on laptop speakers. Measured against the old kit, at the same peak: the kick has 8.7 dB more
  weight below 60 Hz and 2.8 dB more punch; the snare is 3.3 dB louder, with 3.7 dB more body and 2.9 dB more
  crack, and rings 0.4 seconds longer; there is about twice as much grit or more (the clap snare's goes from 18 to
  33 percent of its sound, and the hats had none). In a dubstep beat the backbeat snare now sits 1 dB under the
  kick instead of 3.6 dB. The old kit is not kept (Russell's choice); projects that use it get the new sound. The
  kit file is rebuilt by itself (kit version 3).

**Fixes**
- A song made only of rhythm players can be exported: Export said there was nothing to export (since 0.8).
- A damaged project file can no longer leave a project stuck: impossible numbers and broken rhythm player
  settings are cleaned when it opens.

Tested in Claude's workspace and the laptop's Linux shell. An independent reviewer read the whole of 0.9.2 three
times; its findings are fixed with tests. The most serious were in the Step pattern window: it did not start
from what is heard, and editing a part's step changed the whole part. Not yet run on Windows.

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

### In detail

**Moving around the project window**
- **F6 and Shift+F6** jump to the next and previous area, going round in a circle in the order they are on
  screen: Tracks, Regions, the Musical keyboard, the keyboard controls, each button group and Status. Areas
  that are hidden or empty are skipped. Each jump says where you landed and what is there ("Track group, 11
  buttons, 3 check boxes"); while recording it stays quiet. Control+1 to Control+5 work as before.
- **"selected"**: the track and the region you are on end with ", selected" in the Tracks and Regions lists,
  on screen and spoken ("Track 1, Piano, selected"). In selection mode (Shift+F8) the word keeps meaning
  "marked with Space". Up, Down, Page Up, Page Down, Home and End in those lists are handled by Musician Forge
  itself, so the words change before the list moves and the screen reader reads the item you land on once.
- **Recent projects only show**: on the start screen, Enter or a double-click in Recent projects no longer
  opens a project (Enter says how to open one), so a stray Enter never opens the wrong project. Open project
  lists the recent projects first, marked "Recent", with the one you were on already selected, then every
  other project in Musician Forge Songs, newest first.

**Importing audio and MIDI files**
- **Audio files of every common kind**: WAV, MP3, M4A, MP4 and AAC, FLAC, Ogg Vorbis, Opus, AIFF, Apple
  Lossless and Windows Media Audio. Most are read by libsndfile, which comes with the FluidSynth download
  (nothing new to install); M4A, AAC and Windows Media Audio by Windows' own decoders. A file with the wrong
  ending still imports; a damaged, empty or missing file says why in words and adds nothing (an M4A on a
  Windows N edition names the Media Feature Pack). The whole import, reading, converting to 48 kHz and saving
  Musician Forge's own copy, runs in the background a piece at a time, so a long file needs little extra memory
  and the progress window keeps talking; Escape cancels at any point and leaves nothing behind. The original
  file is never changed.
- **MIDI files** (type 0 and type 1): each MIDI track with notes becomes a track with its instrument (channel
  10 becomes drums), with volume and pan, and their changes as automation; instruments and mix set up in a
  track of their own (as many files do) are found. A window says what the file holds and whether to use its
  tempo changes, time signatures, keys and markers (markers become sections; on for a project with nothing
  set up yet). Running status, notes struck again before they end (cut where they are struck again, as the
  synthesizer plays them), a first tempo after the start (120 until then) and damaged files are handled;
  Control+Z takes the whole import back.
- Control+Shift+I imports either kind; the Recordings list's Insert imports audio.

**Recording sound**
- **The lost take is found and fixed** (Russell, 8 October: recording from bar 1 to bar 9 in an 8-bar section
  seemed to lose the take). The short bit recorded after the loop came round became the take that played, so
  only a second or two was heard. Now the newest complete pass plays, the short bit is kept as a take of its
  own, and Musician Forge says so. A new take on a trimmed recording plays whole. Tested end to end.
- **Hearing yourself stays close to live**: after a hiccup, the sound waiting to be heard no longer stays
  behind for good; it catches up with a short crossfade. How close it stayed is written in the log.
- **Low-latency hearing yourself** (Options, Audio settings; Windows 10 and later; off unless you turn it on):
  hearing yourself takes a shorter way, through Windows' low-latency shared streams (IAudioClient3, reached
  directly because PortAudio cannot ask for them), at the shortest period the sound driver allows (often 2.7
  ms). You hear the microphone with the track's volume and pan, without its effects. Shared mode, so the
  screen reader keeps talking. When Windows cannot give it, Musician Forge says why once and you hear yourself
  as before; if a headset is unplugged mid-take, the usual way takes over. "Check low-latency support" and
  Diagnose say what the sound card allows (they only read).
- **Raw microphone sound** (on unless you turn it off in Audio settings): Musician Forge asks Windows for the
  microphone without its noise reduction and other processing, which can remove held notes and the sound of
  the room. A microphone that refuses raw sound is opened without it, never swapped for another. The microphone test says when the microphone goes almost completely silent between sounds (a sign
  of noise reduction) and how to turn Windows' enhancements off; Diagnose reads each microphone's enhancement
  setting (only reads).
- **Measure the recording delay is remembered for each output and microphone pair** (a measured or typed
  adjustment, never one just carried over), and Audio settings says when a pair has not been measured yet, or
  looks like Bluetooth.
- **Pitch correction sounds clearer**: only what really needs moving is processed (breaths, noisy stretches
  and notes already within 8 cents play exactly as recorded, with short crossfades); octave mistakes in the
  pitch reading are put right first; the slices are cut at the same point of each cycle and joined with short
  crossfades. Measured on a sung "ah" with background noise: 6.5 dB lost between 4 and 8 kHz before, 0.4 now.

**Smaller changes**
- Run Tests' guitar pack stage no longer prints the harmless "No preset found on channel 9" line.
- The help (F1) and the Read Me describe all of the above, and give the honest limit: hearing yourself
  through a computer always takes a moment; for none at all, use direct monitoring on a USB microphone or
  audio interface, with wired headphones.

Tested in Claude's workspace and the laptop's Linux shell (every test, including new ones for each item), then
reviewed line by line by a second reviewer, whose twelve findings are fixed with tests (the most serious: the
low-latency streams read Windows' sound format from the wrong place and could never have started). The
Windows-only parts (low-latency streams, Media Foundation import, raw microphone sound) have Windows tests that
run in Run Tests on the laptop.

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

### In detail

**New name (8 October 2026)**
- The program, which was called Melody Forge, is now **Musician Forge**. The launchers are "Install or Update
  Musician Forge" and "Start Musician Forge"; your songs folder is Documents\Musician Forge Songs and the
  data folder is %LOCALAPPDATA%\MusicianForge. The first Install or Update after the change renames your old
  folders (Melody Forge Songs and MelodyForge) in one step, with everything inside, and keeps your recent
  projects list. Project files still end in .mforge, so every project opens as before.

**Automation**
- A track's volume, pan and effect settings can now change over time.
  Control+Shift+U, or the new Automation button in the Track group, lists the
  track's lanes (Volume, Pan, or one setting of one of its effects); each lane
  lists its points, read out as "Bar 5, beat 1: volume 80, glides to volume 40
  by bar 9, beat 1". Points glide to the next one or hold until it.
- Write automation (Control+Shift+W, or the new check box in the Track group):
  while the song plays, changing volume, pan, Track settings or an effect's
  settings writes points where you hear them. Playing over a place again
  replaces what you cross; a whole play-through undoes in one step.
- Automation is heard straight away, saved in the project, included in WAV and
  M4A exports, and written into MIDI exports as volume and pan controller changes.
- Effects keep their automation when they are moved up or down the list;
  removing an effect removes its lanes (Control+Z brings both back).

**Smaller changes**
- Changing a track's volume, pan or effects while the song plays no longer cuts
  off notes that are sounding.
- A guitar pack chosen while the song plays is played by the stand-in until you
  stop (its samples take most of a second to get ready), so playback never
  stutters.
- Swing now moves the notes between the swung ones too, so drum fills stay clean.
- Region settings only trims a region when its start or end was changed.
- Menus: every item in a menu now has its own underlined letter (Export audio,
  Duplicate, Speak position, Section settings and Speak keyboard settings got
  new letters).
- A project can now have up to 100 tracks (it was 60). The instrument engine now has 128 channels, so
  every track still has its own sound for its effects, volume and pan (measured: about 0.07 milliseconds
  more work per audio block, out of 5.3).
- Run Tests starts with a sound engine check: twenty-one small steps, each in a program of its own, from
  loading FluidSynth to playing a song, so a crash in the instrument engine is pinned to one step
  (logs\engine_probe.txt). It refuses to run on the wrong Python (it says to run Install or Update first),
  and its window now waits for a key instead of closing by itself.
- **The Windows crash is found and fixed.** From 0.7 on, Musician Forge gives every track its own sound output
  in the instrument engine. The Windows downloads of FluidSynth 2.6 (and the "cpp11" ones of 2.5) reserve too
  little memory for the list of outputs when there are three or more: a pair of brackets is missing in
  FluidSynth's own code, so it writes past the end the first time it makes sound and Windows ends the program
  (exit code 0xC0000409). Linux builds are not affected, which is why it never happened in testing there.
  Install or Update now installs **FluidSynth 2.5.7**, the official Windows download built with GLib, which
  reserves the right amount (checked in its source, in the machine code of the Windows DLL, and by building it
  the way Microsoft's compiler does, which passes all 21 steps of the sound engine check). It replaces 2.6.1 by
  itself. The download is checked first (its exact size, every file inside intact, GLib next to the engine) and
  unpacked beside the old engine, and only then are the two swapped, so a cut-off download, a full disk or a
  Musician Forge window still open leaves the old engine as it was and says what to do. A missing engine file
  (removed by antivirus, say) is put back by the next Install or Update. Musician Forge refuses a
  crashing build with words instead of crashing (it then uses its simple built-in synthesizer), and Diagnose
  names the installed build.
- Install or Update: when the last step (the self check) is ended by Windows without a report, as happened on
  8 October (exit code 0xC0000409), the installer now says so, lists the checks that did pass, names the last
  call it made into the instrument engine, and runs the sound engine check to show which calls crash. Before,
  it printed the previous day's report, which said everything was fine. The instrument engine keeps a trail
  of every call it makes (logs\selfcheck_trace.txt and logs\engine_probe_trace.txt), written before each call,
  because Windows ends the program at once in this kind of stop and Python's own crash report cannot see it.
- Run Tests now runs every test file in a program of its own. If the sound engine ever crashes the program
  (as it did on 8 October), only that file stops: the report is still written, names the file and the test,
  and logs\test_crash.txt says which line of code it was.
- Run Tests, from the 8 October evening run: the guitar pack stage now speaks as it goes, including each
  pack's download every 25 percent. Before, its words waited until the stage ended, so after "Tests finished"
  the window seemed done for minutes and was closed during the stage. The tests' summary now says "Tests done"
  and asks you to keep the window open, and the very last line is "Run Tests is finished". A stage stopped
  half way (by closing the window) no longer leaves its download in the temporary folder: the next stage
  removes it. Run Tests' own two crash tests, which only passed on Linux, now crash the program on Windows
  too (there, their old way of crashing became an ordinary Python error, so the program carried on).
- Projects saved by 0.9 open in 0.9 and later (file version 7).

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

### In detail

**Rhythm players**
- Five rhythm players play parts for you: Anvil (drums), Bellows (bass), Ember
  (keys), Spark (synth) and Hammer (guitar). Control+Shift+R, or the New rhythm
  player button in the Track group, adds one on a new track or the selected
  track, for the section the playhead is in, the whole song, or bars you choose.
- Anvil has eleven drummers: Electronic (dubstep, house, trap), Acoustic (rock,
  hard rock, metal, jazz, funk, pop) and Percussion (hand percussion, shakers and
  tambourine), each on a fitting kit. Two new kits of Musician Forge's own: the
  Forge House Kit and the Forge Trap Kit.
- Enter on a rhythm player region opens its editor: Style, Patch (any instrument
  or kit), Intensity, Complexity, Fills, Swing, Follow, Follow amount, Hit
  sensitivity and the Variation number. Every change is heard at once and undoes
  with Control+Z, also inside the editor.
- Reforge (Control+R in the editor; R or Control+R on the region in the Regions
  list) plays a different
  performance with every setting kept; Previous variation goes back. The same
  settings always play exactly the same notes.
- Follow: a player can follow another track, including a recorded audio track,
  whose hits Musician Forge finds by itself. Drums land their kicks on the
  followed part's strongest hits; the others lock their rhythm to it.
- Turn into notes makes a performance into ordinary notes you can edit.
- Rhythm players are heard in playback and included in WAV, M4A and MIDI exports.

**The chord track**
- Control+Shift+H, or the Chord track button in the Song group: the song's
  chords, which rhythm players play. Add, edit and delete chord changes; fill
  bars from a common progression in the song's key (it follows key changes);
  work the chords out from a track you played; clear bars. The Status says the
  chord at the playhead.

**Guitar sounds**
- Two distorted electric guitar packs by FreePats (public domain) for Hammer and
  for playing by hand. The installer downloads them (two new steps, each checked
  by size). Without the internet the install still finishes, the packs are
  listed as "not downloaded yet", a stand-in guitar plays, and Musician Forge
  downloads them by itself the next time it starts online, saying when each is
  ready. Diagnose reports their state. Run Tests has a new stage that downloads
  each pack into a temporary folder, checks it, plays a note and deletes it.

**Trimming and looping regions**
- Alt+Enter in the Regions list (or the Region settings button): change where a
  region starts and ends, and play it several times in a row or until the next
  region. Recordings can be trimmed and lengthened again, and looped too.

## 0.7.0 (8 October 2026, in testing)

### New features and improvements

- Effects on every track: EQ, compressor, distortion (with a bit crusher), delay and reverb, plus pitch correction
  on audio tracks, with 36 presets.
- Measure the recording delay, so recordings land on the beat.
- Separate timing adjustments for the musical keyboard and the microphone.
- Each track's sound is processed on its own.

### Bug fixes

- No bug fixes in this version.

### In detail

**Effects on every track**
- Control+F, or the new Effects button in the Track group, opens the selected
  track's effects. The sound goes through them from top to bottom, then through
  the track's volume and pan. The Tracks list says how many effects a track has.
- Five effects for every track: EQ, compressor, distortion (soft, hard, fuzz and
  bit crusher), delay (in time with the song, or in milliseconds, with
  ping-pong) and reverb. Audio tracks also have pitch correction, which pulls a
  recording onto the notes of the song's key (it follows key changes), with
  Speed and Strength settings.
- Every effect starts from a preset (36 in all, from "Vocal booth" to "Dubstep
  growl") and every setting can be changed: number boxes that step with the
  arrow keys and say the value, sliders for percentages, lists and check boxes,
  each with a clear name. Changes are heard straight away; a Play or stop
  button in the settings window lets you listen. OK keeps them, Cancel puts
  back what was there, and every change undoes with Control+Z.
- Effects are saved in the project and included in exports.

**Measuring the recording delay**
- Options, Audio settings has a new "Measure the recording delay" button: it
  plays eight clicks through the speakers, listens with the microphone, and
  sets the new Microphone timing adjustment so recordings land on the beat. An
  untrustworthy measurement (clicks not heard clearly) changes nothing and says
  what to try.
- The musical keyboard and the microphone now have separate timing
  adjustments, so fixing one never moves the other.

**Under the hood**
- Each track's sound now comes out of the instrument engine separately, so
  its effects, volume and pan are applied to it alone. Volume and pan sound the
  same as before (the same curves, measured).

## 0.6.0 (7 October 2026, in testing)

### New features and improvements

- Regions on every track, listed after Tracks, with cut, copy, paste, duplicate, split, join, mute, rename and
  move.
- Selection mode (Shift+F8): cut, copy, paste, duplicate, delete, mute and solo work on everything selected.
- Whole tracks can be cut, copied, pasted and duplicated.
- The help recommends wired headphones.

### Bug fixes

- No bug fixes in this version.

### In detail

**Regions**
- Every track now has regions, listed right after Tracks in the project window
  (Control+5). Each region says its name, its sections, where it starts and ends,
  how long it is in bars, and how many notes it holds. Recordings on audio tracks
  are listed the same way.
- Recording makes a region that covers exactly what you recorded: the looping
  section, or from the bar where you started to the bar after you stopped, across
  sections when All sections is on. Regions it overlaps get shorter around it.
- Enter opens a region's notes in the event list (or a recording's settings).
- Cut, copy, paste and duplicate regions (Control+X, C, V and D in the Regions
  list); paste goes at the playhead and replaces what was there. Delete, split at
  the playhead (S), join (J), mute (M) and rename (F2). Move region moves one to
  another bar. Every change undoes with Control+Z.
- Projects from earlier versions get one region for each section that has notes.

**Selection**
- Shift+F8, or the new Select check box in the Edit group, turns selection on, and
  Musician Forge explains how it works. Space then selects or unselects the track or
  region you are on, and says how many are selected. Cut, Copy, Paste, Duplicate,
  Delete, Mute and Solo work on everything selected. Control+A selects them all.
- Whole tracks can be cut, copied, pasted and duplicated too (Control+X, C, V and D
  in the Tracks list, or the Edit buttons).
- New Region group: Open region, Move region, Split, Join, Mute region, Rename region.

**Help**
- The Read Me and the keyboard shortcuts now recommend wired headphones: Bluetooth
  headphones delay the sound by a fifth of a second or more.

## 0.5.1 (7 October 2026, in testing)

### New features and improvements

- M4A export (AAC), about a tenth of the size of WAV, good for sharing and Apple devices.
- The install self check tests M4A export.

### Bug fixes

- No bug fixes in this version.

### In detail

**M4A export**
- Export audio (Control+E, or the Export audio button) now offers two formats:
  WAV (full quality) and M4A (AAC at 192 kbps, about a tenth of the size, good
  for sharing and for Apple devices). Musician Forge remembers the format you chose.
- M4A uses the AAC encoder built into Windows, so nothing extra is installed.
  On the rare copies of Windows without it (N editions without the Media Feature
  Pack), Musician Forge says so, and WAV export still works.
- The install self check tests M4A export too.

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

### In detail

**Audio tracks: record your voice or any instrument**
- New audio track (Control+U, or the New audio track button). R records from the
  microphone with the same count-in, metronome and section looping as instrument
  tracks. Recordings line up with the beat: Musician Forge allows for the sound
  card's delays on the way out and on the way in.
- Each pass over a looping section becomes a take, and the newest plays. A
  punch-in partway through a section keeps its place. Recording over part of an
  older recording replaces just that part; the older one carries on where the new
  one ends. The track being recorded stays quiet so its old takes don't get into
  the microphone.
- The recordings list (Control+L on an audio track): every recording says its
  section, where it starts, where it ends and how long it is, in bars and beats
  and in seconds, which take plays and its gain. Enter changes them, Space plays
  from a recording, Insert imports a WAV file, Delete removes it.
- Import WAV files (Control+Shift+I): 16-bit or 24-bit, any sample rate. Musician
  Forge keeps its own copy.
- Options, Audio settings: choose the microphone, and Test the microphone (it
  says in words whether the level is good, too quiet or too loud, or whether
  Windows is blocking the microphone). A silent, very quiet or clipped
  recording is always pointed out.
- Track settings for audio tracks: record in stereo; hear yourself while
  recording (for headphones).
- WAV exports include audio tracks.

**A folder for each project**
- Musician Forge Songs, then a folder named after the project with the project
  file, a Recordings folder and an Exports folder.
- Musician Forge's own Save project as window (a name, and Choose another folder)
  and Open project window (every project in Musician Forge Songs, newest first,
  with when it was saved, plus Browse).
- Exports go into the project's Exports folder.

**Export**
- New check box: Let the sound ring out after the end. On (the default), the
  export runs until held notes and reverb fade to silence, up to 10 seconds; off,
  it ends exactly at the end of the song. Musician Forge remembers your choice.

**Fixes**
- The keyboard controls had their labels shifted by one control, so a screen
  reader called the Scale box "Layout", the Octave box "Scale", and so on, and
  two boxes had no name. Fixed, and a new test checks that every list, choice
  and text box in every window has its own label right before it.
- Move up and Move down buttons in the Track group (Control+Up and Control+Down
  in the track list still work).

## 0.4.0 (7 October 2026, in testing)

### New features and improvements

- The Forge Dubstep Kit: drum sounds made inside Musician Forge, with no outside samples.
- The Forge 808 Sub bass.
- The drum layout speaks the kit's own sound names.

### Bug fixes

- No bug fixes in this version.

### In detail

**Musician Forge's own sounds**
- Forge Dubstep Kit (Drum Kits): hard-hitting sounds made from scratch inside
  Musician Forge, with no outside samples and no license limits. Kicks with a soft
  and a hard layer, a deep 808 kick, huge snares, claps, a clap snare, a rim snap,
  hats that cut each other off, 808 toms, crash, ride, ride bell, an impact, a riser,
  a reverse cymbal, a shaker and an 808 cowbell. Hits ring out even after a
  quick tap.
- Forge 808 Sub (Bass family): a long, deep 808 bass to play as notes,
  driven enough to be heard on laptop speakers and earbuds.
- The drum layout speaks the kit's own names where they differ (U is impact,
  O is riser, Y is reverse cymbal, I is shaker). Shift+F1 lists them.
- The kit is built the first time Musician Forge starts (under a second) and
  loads next to GeneralUser GS. The install self check tests it too.

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

### In detail

**Start screen and projects**
- Musician Forge opens on a start screen, "Choose a project", with New project,
  Open project, Recent projects and Quit. A project opened directly (a file
  given when starting) still opens straight away.
- Close project (Control+W, or the Close project button in the File group) asks
  to save any changes, then goes back to the start screen.
- Files are now called projects everywhere: New project, Open project, Save
  project, Close project. The folder keeps its name, Musician Forge Songs.
- Recent projects that were deleted or moved drop out of the list, and opening
  one explains that it is gone.

**Musical keyboard**
- Show keyboard controls button right after the musical keyboard (Control+4 goes
  straight there): Layout, Scale, Octave, Velocity, Arpeggiator, Arpeggiator
  pattern, Arpeggiator speed and Arpeggiator octave range. Every control is
  reachable with Tab, and the keys still work.
- Chord strips layout: A to K play the key's 7 chords plus a borrowed chord
  (B flat in C major, E major in A minor), each with its root in the bass.
  Number keys 1 to 8 play the bass notes. Chords follow key changes.
  Control+J says which chord is on each key.
- Scale choice for the keyboard (blues, Dorian and so on), starting on the song
  key's root note.
- B now cycles piano, scale and chord strips.
- Arpeggiator (Control+Shift+P): up, down, up and down, down and up, as played,
  random; quarter notes to 32nd notes; 1 to 4 octaves. It runs inside the sound
  engine, so its notes land exactly on the beat, and every note it plays is
  recorded.

**Buttons and keys**
- New Edit group: Undo, Redo, Quantize, Go to bar.
- New Help group with a Help menu button (also on the start screen): Keyboard
  shortcuts, Musical keyboard layouts, Quick start guide, What's new, Credits and
  About. The Help menu in the menu bar has the same pages.
- In choice lists and text boxes, R and Enter now do their usual job instead of
  starting a recording or jumping to the start.

**Music theory**
- Key names match their key signatures: D flat major (5 flats), C sharp minor,
  G sharp minor, and E flat minor now has 6 flats instead of 6 sharps.
- The key root list names both spellings where both are common, for example
  "C sharp or D flat".

## 0.2.1 (7 October 2026)

### New features and improvements

- After every save or export, Musician Forge says which folder it went into.
- Every save, open, export and recovery is written to the log.

### Bug fixes

- Fixes an export going into the wrong folder: Save As and exports always start in the project's folder or in
  Musician Forge Songs.
- Fixes the tests creating folders in the real Documents folder.

### In detail

- Save As and both exports always start in the project's own folder or in
  Musician Forge Songs. The last export folder is no longer remembered (an export
  had gone into Documents\.claude).
- After every save or export, Musician Forge says the folder, for example "Saved
  My Song.mforge in Musician Forge Songs".
- Every save, open, export and recovery is written to musicianforge.log.
- The accessibility check opens Windows' own Save windows and confirms they start
  in Musician Forge Songs. It now records it when Musician Forge was open.
- Tests no longer create folders in the real Documents folder.
- Confirmed on Windows: a project saved, reopened and exported as a WAV, all in
  Musician Forge Songs.

## 0.2 (7 October 2026)

### New features and improvements

- Buttons in named groups.
- Song sections that loop, with All sections to play the whole song, and recording that layers each pass.
- Rewind and Forward say when you reach a section's edge.
- Quiet recording: nothing is spoken when recording or playback starts.

### Bug fixes

- No bug fixes in this version.

### In detail

- Buttons in named groups: Transport (with Rewind and Forward, one bar each),
  Track, Song and File.
- Song sections: every new project is one 8-bar section; no limit
  on sections; Space loops the current section, All sections plays everything;
  recording loops and layers passes, one undo per take; Automatic switch lets a
  section grow for long takes. Section names become MIDI markers.
- Rewind and Forward announce section edges ("Bar 8, end of Section 1"), but not
  while recording.
- Quiet recording: nothing is spoken when recording or playback starts.
- Windows results: 217 tests passed; accessibility check 17 windows, 289
  controls, 0 problems; 0 audio dropouts.

## 0.1 (7 October 2026)

### New features and improvements

- The first working version: musical typing on the computer keyboard (piano, scale and drum layouts), FluidSynth
  with GeneralUser GS, tempo, time signature and key changes, the event list, quantize, WAV and MIDI export,
  autosave and crash recovery, and support for NVDA, JAWS and Narrator.

### Bug fixes

- None: the first version.

### In detail

- First working version: laptop-key musical typing (piano layout), scale
  mode, drum layout, FluidSynth with GeneralUser GS, tempo, time signature and
  key changes, event list, quantize, WAV export (48 kHz, 24-bit) and MIDI export,
  autosave and crash recovery, NVDA, JAWS and Narrator support.
