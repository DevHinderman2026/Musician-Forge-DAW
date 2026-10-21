# Musician Forge Guide for Testers

For people trying Musician Forge 0.9.6 before its first release.

Thank you for testing. Musician Forge is a music program for Windows made to work fully with screen readers (NVDA, JAWS and Narrator). This test version needs Python from python.org (see [Before you start: Python](#before-you-start-python)); the 1.0 release will have a normal installer and will not. This guide says how to install it, what to try in about an hour and a half, and how to send back what you found. Nothing here changes your Windows settings.

## How this guide works

Every test is a step with its own heading, so with a screen reader you can move from step to step by heading (H in NVDA and JAWS, or 3 for the steps alone). Each step has two parts:

- **What to check:** what to do.
- **What to expect:** what should happen. If something else happens, or something is silent, slow, unclear or not read out by your screen reader, note it.

Take the parts in order. The optional parts can be skipped.

## Which copy to download

On Musician Forge's GitHub page, choose Code, then Download ZIP. That copy (the main branch) has everything you need: the program, Install or Update Musician Forge, Start Musician Forge, the Read Me and this guide. You do not need the development branch: it adds the automated tests and the tools the people building Musician Forge use.

## Before you start: Python

- Install Python 3.10 or newer, 64-bit, from python.org (Downloads, Windows). In the installer's first screen, tick "Add python.exe to PATH", then choose Install Now.
- The Microsoft Store's Python does not work: it quietly moves the files Musician Forge makes into a private folder. If it is the only Python on the computer, the installer says so and stops; install the python.org one as above (both can stay installed).

## What you need

- A Windows 10 or 11 computer (64-bit).
- Python, as above.
- About 2 GB of free disk space: most of it is the instrument sounds.
- The internet for the install: it downloads about 500 megabytes (the instrument engine, the main sounds, and two electric guitar packs).
- Wired headphones are best. Bluetooth headphones add a delay you can hear.

## Installing

1. Unzip the Musician Forge folder wherever you like, for example in Documents.
2. Open the folder in File Explorer, select "Install or Update Musician Forge" and press Enter (or double-click it). If Windows asks whether to run it, choose Run (or More info, then Run anyway).
3. A console window reads out each step, "Step 1 of 7" to "Step 7 of 7". It ends with a self check that plays a test note silently and says whether everything works. Press any key to close the window.
4. The two guitar packs (steps 5 and 6) are the biggest downloads and take a few minutes. If they are very slow, let them run; or close the window and run Install or Update again later, which picks up where it stopped. Without them Musician Forge still works: a stand-in guitar plays, and the packs download by themselves the next time Musician Forge starts with the internet, saying when each is ready.
5. Run "Start Musician Forge" the same way. It opens on the start screen: choose New project.
6. Press F1 at any time for every keyboard shortcut.

To update to a newer test version, put its files in the same folder and run "Install or Update Musician Forge" again. Your projects are kept (they are in Documents, Musician Forge Songs).

## Part 1: Getting around (5 minutes)

### Step 1.1: Tab through the project window

**What to check:** Press Tab from the top of the project window and go all the way round: Tracks, Regions, the Musical keyboard, Show keyboard controls, the Transport, Track, Edit, Region, Song and Menus groups, and Status.

**What to expect:** Every control has a clear name, and each group says its name. The Menus group's buttons open the menus (File, Region, Track, Transport, Song, Keyboard, Options and Help).

### Step 1.2: Jump from area to area

**What to check:** Press F6 a few times, then Shift+F6.

**What to expect:** Each jump says where you are, for example "Track group, 11 buttons, 3 check boxes", and the jumps go round in a circle.

### Step 1.3: Jump straight to an area

**What to check:** Press Control+1, Control+5, Control+2 and Control+3.

**What to expect:** They go to Tracks, Regions, the Musical keyboard and Status.

### Step 1.4: The Tracks list

**What to check:** Arrow up and down the Tracks list.

**What to expect:** The track you are on ends with ", selected", read once.

## Part 2: Playing and recording notes (10 minutes)

### Step 2.1: Play the computer keyboard

**What to check:** Press Control+2, then play the letter keys: A S D F G H J K are white keys.

**What to expect:** You hear notes as you press the keys, with no delay you notice.

### Step 2.2: Record

**What to check:** Press R to record a few bars after the count-in, then R to stop. Then press Space.

**What to expect:** A new region in the Regions list, and Space plays it back.

### Step 2.3: The keyboard layouts

**What to check:** Press B a few times while on the Musical keyboard.

**What to expect:** It says each layout (piano, scale, chord strips and the rest), and the keys play that layout.

## Part 3: Effects (10 minutes)

### Step 3.1: Add an effect

**What to check:** On a track, press Control+F. Press Alt+A to add an effect and choose Reverb, Hall.

**What to expect:** The effect is added to the list and its name is read out.

### Step 3.2: Change it while the song plays

**What to check:** Press Enter on the effect to open its settings. Play the song with the Play button (Transport group) and move the Mix slider.

**What to expect:** You hear the change at once.

## Part 4: Rhythm players (20 minutes)

### Step 4.1: Chords for the players

**What to check:** Press Control+Shift+H (Chord track) and choose Fill from a progression, for example one, five, six, four, over bars 1 to 8.

**What to expect:** It says the chord track is filled, with the chords it added.

### Step 4.2: Add the players

**What to check:** Press Control+Shift+R and add Anvil (drums), style Rock. Then add Bellows (bass) and Hammer (guitar) the same way.

**What to expect:** Each player gets its own track and region, and they play the chords together.

### Step 4.3: Variations

**What to check:** In the Regions list, press Enter on a player region to open its editor, and try a few variations.

**What to expect:** Each is a different groove, described in words, and the Regions list says, for example, "variation 3 of 6".

### Step 4.4: Reforge

**What to check:** In the editor, press Control+R a few times.

**What to expect:** It says "Regenerated performance", nothing more. The fills and small details change; the groove stays.

### Step 4.5: Kit pieces

**What to check:** In the drummer's Kit pieces list, arrow through the pieces. Press Space on the Kick. Then press Enter on a piece to open its settings and try When a crash comes, every 4 bars, on the Crash cymbals.

**What to expect:** In a rock groove the Ride, Crash cymbals, Toms and Congas say "off" (the groove doesn't use them). Space on the Kick says "Kick off" and the groove's kicks stop. The crash plays every 4 bars.

### Step 4.6: The Step pattern

**What to check:** In the Snare's settings, open Step pattern (Alt+S). Arrow through the steps, press Space to turn one on or off, and Page Up to make one louder.

**What to expect:** You hear only that change.

### Step 4.7: Changing the variation after making steps

**What to check:** With the snare's steps changed, change the variation. Then press Control+Z.

**What to expect:** A warning that your hand-made steps will reset, with Change and Cancel. After Change, Control+Z brings them back.

### Step 4.8: Follow

**What to check:** In the drummer's editor, set Follow to follow the bass track.

**What to expect:** The kick follows the bass's strongest notes.

### Step 4.9: The Forge Dubstep Kit

**What to check:** Add Anvil with the style Dubstep and play it.

**What to expect:** A deep, heavy kit that sounds like dubstep.

## Part 5: Trimming and looping (5 minutes)

### Step 5.1: Loop a region

**What to check:** In the Regions list, press Alt+Enter on a region and make it play 4 times.

**What to expect:** The region's line says "loops 4 times, to bar ...", and it plays 4 times.

## Part 6: Automation (10 minutes)

### Step 6.1: A volume fade with points

**What to check:** On a track, press Control+Shift+U. Press Alt+A to add a lane and choose Volume. In the points list, Alt+A adds a point: add one at bar 1 with 100 and one at bar 5 with 20. Play from bar 1.

**What to expect:** A smooth fade.

### Step 6.2: Write automation while playing

**What to check:** Press Control+Shift+W to turn on Write automation. Play the song and press the right bracket and left bracket keys in the Tracks list (volume up and down). Stop. Then press Control+Z.

**What to expect:** The Volume lane has points where you pressed, and Control+Z undoes the whole pass.

## Part 7: Importing, saving, exporting and more (10 minutes)

### Step 7.1: Import a file

**What to check:** Press Control+Shift+I (or File menu, Import audio or MIDI file) and import an audio file (MP3, M4A, WAV and more) or a MIDI file.

**What to expect:** It says what it made and where. A long file shows its progress, and Escape cancels.

### Step 7.2: Save and export

**What to check:** Press Control+S to save. Control+E exports a WAV or M4A file; Control+Shift+E exports MIDI.

**What to expect:** Musician Forge says where each file went.

### Step 7.3: Nudge and trim regions

**What to check:** In the Regions list (Control+5), Alt+Right and Alt+Left nudge a region; right bracket and left bracket move its start; Shift+right bracket makes it longer, Shift+left bracket shorter; N changes the step. On a rhythm player region, make it longer and play it.

**What to expect:** Each key says where the region starts or ends, the player fills the new length, and Control+Z undoes.

### Step 7.4: Close and reopen

**What to check:** Change something, then press Control+W (Close project) and choose Yes. Open the project again.

**What to expect:** Your change is there.

### Step 7.5: Sections

**What to check:** Add a section (Song group, Sections), move into it, then press Enter and comma a few times. Then turn on All sections (Transport group) and press Enter.

**What to expect:** You stay in that section ("Start of Section 2"). With All sections on, Enter goes to the start of the song.

### Step 7.6: Choosing an instrument

**What to check:** Press Control+I (Instrument) and look through the families.

**What to expect:** The drum kits are only in Drum Kits.

### Step 7.7: Your own chord strips

**What to check:** Press Control+Shift+J, change a chord strip (Enter), then press B until the chord strips layout and play that key.

**What to expect:** Your chord plays.

### Step 7.8: Opening a recent project

**What to check:** On the start screen, press Enter on a recent project.

**What to expect:** It says "Opening" and the project opens.

### Step 7.9: Opening where you left off

**What to check:** Move into section 2 or later and save, close the project and open it again.

**What to expect:** It says that section and bar, and you are there.

### Step 7.10: A player region for a new section

**What to check:** With a rhythm player on a track, add a section, move into it, and press P in the Regions list.

**What to expect:** A player region of the same player and style fills the section, starting from that style's own settings.

### Step 7.11: A drummer has two hands

**What to check:** On a rock drummer, listen to a crash.

**What to expect:** The hi-hat stops for that beat.

### Step 7.12: Other time signatures

**What to check:** Change a section's time signature to 3/4, then 6/8 (Control+Shift+M), and play a drummer and a bass there.

**What to expect:** They play in that meter.

### Step 7.13: Swung fills

**What to check:** Set a drummer's Swing feel to Eighth notes, with Swing at 60 and Fill amount up.

**What to expect:** The fills roll smoothly in triplets.

### Step 7.14: The Menus group

**What to check:** Tab to the Menus group and open a few menus with their buttons.

**What to expect:** The same items as the menu bar (Alt), each read with a comma before its shortcut, and each one works.

### Step 7.15: Headphones in and out

**What to check:** If your computer has a headphone jack, play a song and plug headphones in, then take them out.

**What to expect:** Within a second the sound moves to where Windows plays, and Musician Forge says "Sound now on" and its name.

## Part 8: The microphone (optional, 15 minutes)

### Step 8.1: Choose and test the microphone

**What to check:** Open Options menu, Audio settings (the Options menu button in the Menus group, or Control+Shift+O). Choose the microphone and Test it.

**What to expect:** It listens for 3 seconds while you speak, sing or play, then says what it heard.

### Step 8.2: Measure the recording delay

**What to check:** Options menu, Measure the recording delay (or Control+Shift+D), with headphones off, speakers up and a quiet room.

**What to expect:** It says the delay it measured.

### Step 8.3: Record your voice

**What to check:** Press Control+U to add an audio track, then R to record from the microphone, and listen to the take.

**What to expect:** No pop as the microphone starts.

### Step 8.4: Hearing yourself with little delay

**What to check:** With headphones on, open Track settings on the audio track and tick "Hear the microphone while recording". Then in Options, Audio settings, press "Check low-latency support". If it says your sound card allows it, tick "Low-latency hearing yourself" and record a few notes.

**What to expect:** Less delay than before. Say what you hear.

## Part 9: Removing and reinstalling (optional, last, 10 minutes)

### Step 9.1: Remove Musician Forge

**What to check:** Close Musician Forge and run Remove Musician Forge. Answer Y, then Y to keep your settings.

**What to expect:** It says Musician Forge is removed and your projects are still in Documents, Musician Forge Songs.

### Step 9.2: Install again

**What to check:** Run Install or Update Musician Forge again, then Start Musician Forge and open one of your projects.

**What to expect:** It opens and plays as before.

## New in 0.9.6

### Step N.1: Fills on a steady count

**What to check:** Give a drummer an 8-bar region with Fill amount 50. Reforge it a few times. Then set Fill amount 100 and Fill complexity 100.

**What to expect:** At 50, fills come in bars 4 and 8 only, every time, Reforge included. At 100 with complexity 100, a big fill in every bar. A bass, keys or guitar player follows the same count.

### Step N.2: A human feel

**What to check:** Listen to a rock drummer, straight, then with eighth or sixteenth swing. Then listen to a trap or house drummer.

**What to expect:** The rock drummer sounds less rigid, a little loose like a real drummer. The trap or house drummer stays tight, like a machine.

### Step N.3: Riding the crash

**What to check:** Set a rock drummer's Crash cymbals pattern to a crash in eighth notes.

**What to expect:** The ride and hi-hat stop while the crash keeps time.

### Step N.4: Pieces not in the groove are off

**What to check:** Open a rock drummer's Kit pieces list. Play the region with Fill amount up. Then turn the Kick off with Space.

**What to expect:** The Ride, Crash cymbals, Toms and Congas say "off" (not in the groove), yet the fills still use the toms and the region still starts with a crash. With the Kick off, the groove's kicks stop and the fills' kicks stay.

### Step N.5: Fast hi-hats

**What to check:** Set the tempo to 180 and the Closed hi-hat's pattern to sixteenth notes, then to disco sixteenths.

**What to expect:** Both stay sixteenth notes. (The ride still plays eighth notes above 120 beats a minute.)

### Step N.6: The button groups are back

**What to check:** Tab through the Transport, Track, Edit, Region and Song groups, then open the menus. Try their shortcuts: Control+T, Control+Z, Control+Shift+R and the rest.

**What to expect:** The groups' commands are buttons again and no longer in the menus, and their shortcuts still work.

### Step N.7: Commas in the Menus group

**What to check:** Tab to the Menus group and open a menu with its button.

**What to expect:** Each item is read with a comma before its shortcut, for example "Tempo changes..., Control+Shift+T".

## Added in 0.9.4 and 0.9.5

### Step E.1: Selecting notes in the event list

**What to check:** In a region's event list (Control+L), press Space on two notes, then Control+Up. Then press Control+Q.

**What to expect:** Both notes move. Quantize offers the region you are on, the selected track or all tracks.

### Step E.2: Exporting tracks on their own

**What to check:** Export audio (Control+E) with WAV and What to export "Only the tracks you choose". Press Space on one track and export it; then choose two.

**What to expect:** One WAV file for one track; a zip with one file for each of the two.

### Step E.3: MIDI in another program

**What to check:** Export MIDI (Control+Shift+E) and import the file into another program.

**What to expect:** The instruments (guitar, drums), the tempo, time signature and key are right, and the Chord track is there and silent.

### Step E.4: A kit without a sound

**What to check:** Give a rock drummer the Forge Trap Kit and set its Crash cymbals to the splash.

**What to expect:** The splash plays on the crash; it does not go silent.

### Step E.5: Fills and Complexity

**What to check:** In a drummer's region, set Fill amount to 100 and move Fill complexity high and low. Open the Ride's settings and move its Complexity to 100 and to 0. Reforge a few times.

**What to expect:** Bigger and smaller fills; a busier and a sparser ride; the fills change with each Reforge.

### Step E.6: The hi-hat build

**What to check:** Make two drummer regions one after the other on the same track, the first at Intensity 50 and the second at 100. Then set the first to 100 too.

**What to expect:** The last two bars of the first build on the hi-hat: closed, then half open, then wide open into the second region. With both at 100, the build goes away.

### Step E.7: Editing two regions at once

**What to check:** Select two drummer regions (Shift+F8, then Space on each), press Enter, and move Intensity.

**What to expect:** Both change.

### Step E.8: Reforge

**What to check:** Reforge a drummer region a few times.

**What to expect:** Each time it says only "Regenerated performance", and the fills change.

### Step E.9: One sound per piece

**What to check:** Open the Closed hi-hat's settings.

**What to expect:** There is no "Play this rhythm on" any more: each piece plays only its own sounds.

### Step E.10: The ride in fast songs

**What to check:** Set the song's tempo to 130 and open the Ride's settings. Play it.

**What to expect:** The Pattern list has no sixteenth notes, and the ride plays eighth notes.

### Step E.11: Fade-out and progress

**What to check:** Export audio (Control+E) with "Fade out at the end of the song" on and a fade of 10 seconds. Listen to the end of the file.

**What to expect:** The song fades out over its last 10 seconds. While it exports, it says 10 percent, 20 percent and so on.

### Step E.12: The distortion warning

**What to check:** Turn one track's volume up to 100 and play loud chords on it, then export.

**What to expect:** The message names the bars, how many dB too loud, and that track.

### Step E.13: No pop when recording

**What to check:** Record on an audio track.

**What to expect:** No pop at the very start of the take.

## Sending back what you found

1. Close Musician Forge, so its log is complete.
2. Open the "logs" folder in the Musician Forge folder.
3. Attach these files to an email (or put them in a zip file first):
   - musicianforge.log: what happened while you used Musician Forge.
   - install_log.txt and selfcheck_log.txt, if installing had a problem.
4. Send it to Russell at russellhinderman425@gmail.com, with your notes: the step (for example "Step 4.5"), what you tried, what you expected, what happened, which screen reader you use (and its version), and which version of Windows.

The logs hold no recordings and no songs, only what Musician Forge did, the names of your sound devices, and the folders it used.

## Known limits in 0.9.6

- Musician Forge needs Python until the 1.0 installer.
- The guitar packs play from B1 to D6 (key 35 to 86): drop D, drop C and B standard work; lower notes are silent.
- Rhythm players following a recording work best with clear, separate hits (picked or strummed guitar, piano, drums); slow pads and legato lines have few clear starts.
- In the Step pattern, a step can hold several sounds, but Left and Right keep only one of them (Control+Z brings the others back).
- Low-latency hearing yourself needs Windows 10 or later and a sound driver that offers it; Musician Forge says when it does not.
- Hearing yourself through a computer always takes a moment. For none at all, use direct monitoring on a USB microphone or audio interface.
- Bluetooth headphones add a delay you can hear when playing live.
