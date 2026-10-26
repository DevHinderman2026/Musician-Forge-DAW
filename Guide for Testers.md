# Musician Forge Guide for Testers

For people trying Musician Forge 0.9.11 before its first release.

Thank you for testing. Musician Forge is a music program for Windows made to work fully with screen readers (NVDA, JAWS and Narrator). This test version needs Python from python.org (see [Before you start: Python](#before-you-start-python)); the 1.0 release will have a normal installer and will not. This guide says how to install it, what to try in about an hour and a half, and how to send back what you found. Nothing here changes your Windows settings.

## How this guide works

Every test is a step with its own heading, so with a screen reader you can move from step to step by heading (H in NVDA and JAWS, or 3 for the steps alone). Each step has two parts:

- **What to check:** what to do.
- **What to expect:** what should happen. If something else happens, or something is silent, slow, unclear or not read out by your screen reader, note it.

Take the parts in order. The optional parts can be skipped.

## Which copy to download

On Musician Forge's GitHub page, choose Code, then Download ZIP. That copy (the main branch) has everything you need: the program, Install or Update Musician Forge, Start Musician Forge, the Read Me and this guide. You do not need the development branch: it adds the automated tests and the tools the people building Musician Forge use.

## Before you start: Python

- Install 64-bit Python 3.14 (or 3.13 or 3.12) from python.org (Downloads, Windows). In the installer's first screen, tick "Add python.exe to PATH", then choose Install Now. Python 3.15 does not work yet: wxPython, which Musician Forge's windows use, has no build for it; 3.14 can be installed beside it. On an ARM64 PC, choose the x64 (AMD64) installer.
- The Microsoft Store's Python does not work: it quietly moves the files Musician Forge makes into a private folder. If it is the only Python on the computer (or no suitable Python is found), the installer offers to install Python 3.14 from python.org for you: press Y. It installs for your Windows user only and needs no administrator rights. If you press N, or it can't, it tells you how to install it yourself (both can stay installed).

## What you need

- A Windows 10 or 11 computer (64-bit).
- Python, as above.
- About 2 GB of free disk space: most of it is the instrument sounds.
- The internet for the install: it downloads about 500 megabytes (the instrument engine, the main sounds, and two electric guitar packs).
- Wired headphones are best. Bluetooth headphones add a delay you can hear.

## Installing

1. Unzip the Musician Forge folder wherever you like, for example in Documents.
2. Open the folder in File Explorer, select "Install or Update Musician Forge" and press Enter (or double-click it). If it says to choose Extract All, the files are still inside the zip: extract them first. If Windows asks whether to run it, choose Run (or More info, then Run anyway).
3. A console window reads out each step, "Step 1 of 7" to "Step 7 of 7". It ends with a self check that plays a test note silently and says whether everything works. Press any key to close the window.
4. The two guitar packs (steps 5 and 6) are the biggest downloads and take a few minutes. If they are very slow, let them run; or close the window and run Install or Update again later, which picks up where it stopped. Without them Musician Forge still works: a stand-in guitar plays, and the packs download by themselves the next time Musician Forge starts with the internet, saying when each is ready.
5. Run "Start Musician Forge" the same way (if it says the last Install or Update did not finish, run Install or Update again). It opens on the start screen: choose New project. A new project starts with no tracks, and the New track list opens by itself: press Enter on Instrument, choose Grand Piano and press Enter, so the steps below have a piano track to play.
6. In a project, press F1 for every keyboard shortcut (on the start screen, use the Help menu button).

To update to a newer test version, put its files in the same folder and run "Install or Update Musician Forge" again. Your projects are kept (they are in Documents, Musician Forge Songs). Update Musician Forge before you open a project someone else made, so it plays exactly as they heard it.

## Part 1: Getting around (5 minutes)

### Step 1.1: Tab through the project window

**What to check:** Press Tab from the top of the project window and go all the way round: Tracks, Regions, the Musical keyboard, Show keyboard controls, the Transport, Track, Edit, Region, Song and Menus groups, and Status.

**What to expect:** Every control has a clear name, and each group says its name. The Menus group's buttons open the menus (File, Region, Track, Transport, Song, Keyboard, Options and Help).

### Step 1.2: Jump from area to area

**What to check:** Press F6 a few times, then Shift+F6.

**What to expect:** Each jump says where you are, for example "Track group, 9 buttons, 3 check boxes", and the jumps go round in a circle.

### Step 1.3: Jump straight to an area

**What to check:** Press Control+1, Control+5, Control+2 and Control+3.

**What to expect:** They go to Tracks, Regions, the Musical keyboard and Status.

### Step 1.4: The Tracks list

**What to check:** Add a second track (Control+T, then Instrument, or Audio), then arrow up and down the Tracks list.

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

**What to expect:** It says each layout (piano, scale and chord strips), and the keys play that layout.

## Part 3: Effects (10 minutes)

### Step 3.1: Add an effect

**What to check:** On a track, press Control+F. Press Alt+A to add an effect and choose Reverb, Hall.

**What to expect:** The effect is added to the list and its name is read out.

### Step 3.2: Change it while the song plays

**What to check:** Press Enter on the effect to open its settings. Press Alt+P (Play or stop the song) in the settings window and move the Mix slider.

**What to expect:** You hear the change at once.

## Part 4: Rhythm players (20 minutes)

### Step 4.1: Chords for the players

**What to check:** Press Control+Shift+H (Chord track) and choose Fill from a progression, for example one, five, six, four, over bars 1 to 8.

**What to expect:** It says the chord track is filled, with the chords it added.

### Step 4.2: Add the players

**What to check:** Press Control+Shift+R (or Control+T, then Rhythm player) and add Anvil (drums), style Rock (the Style list says "Acoustic: Rock"). Then add Bellows (bass), style Driving eighths, and Hammer (guitar), style Rock strum, the same way.

**What to expect:** Each player gets its own track and region, and they play the chords together.

### Step 4.3: Variations

**What to check:** In the Regions list, press Enter on a player region to open its editor, and try a few variations.

**What to expect:** Each is a different groove, described in words, and the Regions list says, for example, "variation 3 of 6".

### Step 4.4: Reforge

**What to check:** In the editor, press Control+R a few times.

**What to expect:** It says "Regenerated performance", nothing more. The fills and small details change; the groove stays.

### Step 4.5: Kit pieces

**What to check:** In the drummer's Kit pieces list, arrow through the pieces. Press Space on the Kick. Then press Enter on a piece to open its settings and try When a crash comes, every 4 bars, on the Crash cymbals.

**What to expect:** The list goes Kick, Snare, Clap or rim, Hi-hat, Hi-hat pedal, Toms, Crash cymbals, Ride, Congas and bongos, and Shaker, tambourine, cowbell and claves. In a rock groove the Clap or rim, Hi-hat pedal, Toms ("off, in fills only"), Crash cymbals, Ride, Congas and bongos, and Shaker, tambourine, cowbell and claves say "off" (the groove doesn't use them). Space on the Kick says "Kick off" and the groove's kicks stop. The crash plays every 4 bars.

### Step 4.6: The Step pattern

**What to check:** In the Snare's settings, open Step pattern (Alt+S). Arrow through the steps, press Space to turn one on or off, and Page Up to make one louder.

**What to expect:** You hear that change. The Step pattern holds up to 4 bars, which repeat through the region (it says so), so in an 8-bar region bars 5 to 8 play the same steps as bars 1 to 4.

### Step 4.7: Changing the variation after making steps

**What to check:** With the snare's steps changed, change the variation. Then press Control+Z.

**What to expect:** A warning that your hand-made steps will reset, with Change and Cancel. After Change, Control+Z brings them back.

### Step 4.8: Follow

**What to check:** In the drummer's editor, set Follow to "Another track", then set Track to follow to the bass track.

**What to expect:** The kick follows the bass's strongest notes.

### Step 4.9: The Forge Dubstep Kit

**What to check:** Add Anvil with the style Dubstep ("Electronic: Dubstep" in the Style list) and play it.

**What to expect:** A deep, heavy kit that sounds like dubstep.

## Part 5: Trimming and looping (5 minutes)

### Step 5.1: Loop a region

**What to check:** In the Regions list, press Alt+Enter on a region and make it play 4 times.

**What to expect:** The region's line says "loops 4 times, to bar ...", and it plays 4 times.

## Part 6: Automation (10 minutes)

### Step 6.1: A volume fade with points

**What to check:** On a track, press Control+Shift+U. Press Alt+A to add a lane and choose Volume. Press Enter on the Volume lane (or the Points button, Alt+P) to open its points list. In the points list, Alt+A adds a point: add one at bar 1 with 100 and one at bar 5 with 20. Play from bar 1.

**What to expect:** A smooth fade.

### Step 6.2: Write automation while playing

**What to check:** Press Control+Shift+W to turn on Write automation. Play the song and press the right bracket and left bracket keys in the Tracks list (volume up and down). Stop. Then press Control+Z.

**What to expect:** The Volume lane has points where you pressed, and Control+Z undoes the whole pass.

## Part 7: Importing, saving, exporting and more (10 minutes)

### Step 7.1: Import a file

**What to check:** Press Control+T, choose Import file (or press Control+Shift+I) and import an audio file (MP3, M4A, WAV and more) or a MIDI file.

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

**What to expect:** You stay in that section ("Bar 9, start of Section 2"). With All sections on, Enter goes to the start of the song ("Bar 1, start of Section 1").

### Step 7.6: Choosing an instrument

**What to check:** Press Control+I (Instrument) and look through the families.

**What to expect:** The drum kits are only in Drum Kits.

### Step 7.7: Your own chord strips

**What to check:** Press Control+Shift+J, change a chord strip (Enter), close the window, press Control+2 to go to the Musical keyboard, then press B until the chord strips layout and play that key.

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

## New in 0.9.11

### Step Z.1: Reforge while the song plays

**What to check:** Add a rock drummer, and a Spark (synth) region with the style Pad on a track of its own. Play the song. While it plays, arrow to the drummer's region in the Regions list and press Control+R (Reforge) a few times. Then stop, and press Control+R once more.

**What to expect:** The song keeps playing where it is. Each Control+R says "Regenerated performance", and the new fills and details come in from there on, so you can try one performance after another. The playhead never jumps back, and the pad's long chords keep sounding. Stopped, Control+R plays the region from its start, as before.

### Step Z.2: Held notes, the EQ and the reverb while playing

**What to check:** With the pad playing long chords, press Control+Shift+T (Tempo changes), press Enter on the first tempo change, type a slower tempo and press Enter. Then add an EQ to the pad's track (Control+F, Alt+A) and arrow through its presets while the song plays.

Last, add a Reverb with the Hall preset to the pad's track and, while the song plays, open the reverb's settings (Enter on it) and choose the Small room preset.

**What to expect:** The tempo changes at once and the chord that was sounding keeps sounding, with no new attack and no gap. The EQ presets blend smoothly from one to the next, with no clicks, even when you arrow quickly. The hall's tail rings out by itself after the change, with no click, while the chords that come next sound in the small room.

### Step Z.3: The end of the song

**What to check:** Turn on All sections (Transport group) and play the last few bars of the song. Let it play to its end. Press Space. Let it play to its end again, press Control+S, close the project (Control+W) and open it again.

**What to expect:** It stops at the end and stays there: "End of song, stopped. Bar 17, beat 1" in a 16-bar song (the bar after the last). Space plays the song again from bar 1, and Record would record from bar 1 too. The reopened project is at the end of the song, where it was saved.

### Step Z.4: Asking before replacing

**What to check:** In Tempo changes, press Alt+A, type the bar and beat of a tempo change that is already there and press Enter. Press Escape, then Enter again and answer Yes. Press Control+Z. Try the same in Time signature changes (Control+Shift+M), Key changes (Control+Shift+K), the Chord track (Control+Shift+H) and an automation lane's points (Control+Shift+U, then Enter on a lane).

**What to expect:** It asks first, for example "There is already a tempo change at bar 5, beat 1 (90 BPM). Replace it?". Escape (or No) brings the Add window back with what you typed still in it. Yes replaces it, and Control+Z brings the old one back. Editing a change with Enter never asks.

### Step Z.5: Escape on a Yes or No question

**What to check:** Press Delete on a track in the Tracks list, then press Escape. Do the same on a region in the Regions list.

**What to expect:** Escape answers No: nothing is deleted. Before 0.9.11 these questions could not be closed with Escape.

### Step Z.6: A big MIDI file

**What to check:** Import a MIDI file of a few megabytes (Control+Shift+I). Import it again and press Escape while it is being read. Then import a small MIDI file.

**What to expect:** A window called "Importing MIDI file" says "Reading the MIDI file" and the percentage as it goes. Escape closes it and says "Import cancelled", and nothing changes. A small file shows no progress window at all.

### Step Z.7: Trimmed, and Play keeping the focus

**What to check:** In the Regions list, press Alt+Enter on a region, change "Ends at bar" and press Enter. Then open Recordings (Control+L on an audio track) and Chord strips (Control+Shift+J), Tab to Play in each and press Space twice.

**What to expect:** You hear "Trimmed" first, then the region's line once. In both windows the focus stays on Play, so Space plays and Space again stops.

### Step Z.8: A loop keeps looping

**What to check:** Fill the chord track with chords at bars 1 and 2 only. Add a Spark Pad region over bars 1 and 2 and, with Alt+Enter, make it play 4 times. In the Tracks list, on the pad's track, press Control+G and go to bar 5, press R, play a few notes and press R again in bar 6. Then open Sections (Song group) and press Alt+A on Section 1, so the song has two sections. Add a 2-bar drummer region (Control+Shift+R, How long "Bars I choose", from bar 1 to bar 2) and make it play 8 times (Alt+Enter), then in Sections select Section 1 and press Alt+A again. Last, press Enter on a looping player region and choose Turn into notes.

**What to expect:** Your notes replace bars 5 and 6, and the pad carries on in bars 7 and 8 exactly as the loop played; since the chord track has no chords there, it is written out as notes, and Musician Forge says "The loop carries on after the recording as notes, so it sounds as it did". The second Alt+A says "Added Section 2: bars 9 to 16, 8 bars. The song is now 24 bars long.": the drummer plays bars 1 to 8, the new section's bars are empty for it, and its repeats carry on from bar 17, still a rhythm player, so the loop keeps playing on both sides of the new section. Turn into notes writes out every repeat you hear, as one longer region that no longer loops. Each of these is one Control+Z.

### Step Z.9: The drummer's foot and the percussion

**What to check:** Add a funk drummer, set its Intensity to 80 and play. Then add a rock drummer, turn on its Shaker, tambourine, cowbell and claves with Space, set Fill amount to 100 and play. Last, add a pop drummer and play.

**What to expect:** At Intensity 80 the funk hi-hat is half open, and the Hi-hat pedal holds it there instead of cutting it off, so it rings; the pedal's line in Kit pieces reads "Hi-hat pedal: on, the foot waits for the half-open hi-hat". (From Intensity 85 the hi-hat opens on every stroke and the foot closes it on two and four: see Step Z.17.) The rock shaker plays every one of its sixteenth notes, through the fills too, as if a second player had it. The pop drummer's own tambourine, which plays now and then on sixteenth notes, is heard now.

### Step Z.10: The Ride in metal variations 3 and 4

**What to check:** Add a metal drummer and choose variation 3. In its Kit pieces, press Space on the Ride, then Space on the Ride again. Then press Space on the Hi-hat, Space on the Ride, Space on the Ride again, and Space on the Hi-hat again.

**What to expect:** Space on the Ride says "Ride on with eighth notes, crash off", and the Crash cymbals line begins "Crash cymbals: off, the ride keeps time"; Space again says "Ride off, crash on". Then the Hi-hat says "Hi-hat on with eighth notes, crash off", the Ride says "Ride on, hi-hat off" (it keeps the rhythm it was given), then "Ride off, hi-hat on", and turning the Hi-hat off says "Hi-hat off, crash on". One cymbal always keeps time, and each change is one Control+Z.

### Step Z.11: Following a track that stops

**What to check:** Record a short piano part in bar 1 only. Add Bellows (bass) on a track of its own, and in its editor set Follow to Another track and Track to follow to the piano. Do the same with a drummer. Play.

**What to expect:** In bar 1 the bass and the drummer's kick follow the piano. In the bars after it, where the piano plays nothing, they play their own parts in full instead of two or three scattered notes.

### Step Z.12: 6/8 and arpeggios

**What to check:** Set the time signature to 6/8 (Control+Shift+M). Add Bellows with the style Driving eighths, turn on "Add passing notes into each chord change" in its part's settings, and fill the chord track from a progression. Then add Ember (keys) with the style Ballad arpeggio, put a chord change in the middle of a bar, and play.

**What to expect:** In 6/8 the bass's last eighth before each chord change leads into the new chord. The arpeggio does not go quiet at a chord change in the middle of one of its notes: the next chord's note starts right at the change.

### Step Z.13: Move region keeps its window

**What to check:** In the Regions list, press the Region group's Move region button, type bar 1, beat 9 and press Enter. Then change the beat to 2 and press Enter.

**What to expect:** It says "Bar 1 has 4 beats, so the beat must be from 1 to 4" over the still-open window, with what you typed still in it. The second time the region moves.

### Step Z.14: Undo inside the list windows

**What to check:** Open Effects (Control+F) on a track, add an effect, then press Control+Z and Control+Y without closing the window. Do the same in Tempo changes (Control+Shift+T) after adding a change, in Sections after adding a section, and in an automation lane's points list after adding a point.

**What to expect:** Control+Z undoes the change right there, and the list is read again on the item it was on (or the nearest one); Control+Y brings it back. If an undo takes away the track a window is about, the window closes and says so.

### Step Z.15: The longest a song can be

**What to check:** Open Sections (Song group), press F2 on the last section and set its length so the song is 9995 bars long. Press Alt+A to add a section. Then make the song 9999 bars long and press Alt+A again.

**What to expect:** The first time it says "Only 4 more bars fit: a song can be at most 9999 bars long." The second time it says "The song is already 9999 bars long, the longest a song can be, so no section can be added." Nothing changes either time.

### Step Z.16: A loop stops where the song ended

**What to check:** Record a short part in bars 1 and 2 of a track. In the Regions list, press Alt+Enter on its region and tick "Loop until the next region (or the end of the song)". Open Sections, press Alt+A on the last section, and play the new section. Press Control+Z. Then make the last section longer with F2 and play the new bars.

**What to expect:** The new section is empty: the loop stops where the song ended before, and the new bars are yours to fill. Control+Z puts everything back as it was. Making the last section longer leaves its new bars empty too.

### Step Z.17: The foot under a wide-open hi-hat

**What to check:** Add Anvil with the style Hard rock ("Acoustic: Hard rock" in the Style list). In its Kit pieces, press Space on the Hi-hat pedal and play. Choose variation 4, then variation 5, and play each. Then add a rock drummer, press Space on its Hi-hat pedal, press Enter on the Hi-hat, choose "Open" in How open the hi-hat is, and play. Last, add another rock drummer, press Space on its Hi-hat pedal, choose "Open on every beat" in the Hi-hat's Pattern list, and play.

**What to expect:** Space says "Hi-hat pedal: on, the foot on two and four". In hard rock the hand plays the hi-hat open on its eighth notes, and now the foot is heard: on two and four it closes the hi-hat with a short closed sound, and the open hi-hat rings on the other strokes. The same in variations 4 and 5. Before 0.9.11 the foot played on two and four, but the hand struck the hi-hat open at the same moment, so the foot was hardly heard. In rock with "open", the Hi-hat's line reads "Hi-hat: on, open": the hi-hat rings open on every stroke except on two and four, where the foot closes it. With "Open on every beat" the Hi-hat's line reads "Hi-hat: on, pattern changed": it rings open on one and three, and the foot closes it on two and four. Each change is one Control+Z.

### Step Z.18: The foot waits for a half-open hi-hat

**What to check:** On a rock drummer, press Space on its Hi-hat pedal. Press Enter on the Hi-hat, choose "Half open" in How open the hi-hat is, close the window, listen to the Hi-hat pedal's line and play. Then add a funk drummer (its Hi-hat pedal is on already), set its Intensity to 84 and listen to the Hi-hat pedal's line in Kit pieces. Then set Intensity to 85 and listen again.

**What to expect:** The Hi-hat's line reads "Hi-hat: on, half open", and the pedal's line reads "Hi-hat pedal: on, the foot waits for the half-open hi-hat". Every stroke sounds half open, and no foot cuts it off. In funk, Intensity 84 (half open by intensity, from 70) gives the same line. At 85 (open by intensity, from 85) the line reads "Hi-hat pedal: on, the foot on two and four", and the foot closes the open hi-hat on two and four, as in Step Z.17. Where the foot waits on only some of its steps, the line says so. A metal drummer with its pedal on and the hi-hat half open, for example, reads "Hi-hat pedal: on, the foot on two and four, waiting where the hi-hat is half open".

### Step Z.19: What the octave means in each layout

**What to check:** On a piano track, press Control+4 (the keyboard controls) and Tab to the Octave choice. Press Control+2 and B to go to the Scale layout, and look at the Octave choice again. Then press B again for Chord strips and look once more. Open the Keyboard menu's Octave submenu in each layout. Last, in Chord strips, press Control+2 and Z until it says "Lowest octave", press Control+J, and play A and then 1.

**What to expect:** The Octave choice and the Octave submenu say what the octave does in the layout you are in, as Control+J does. In the Piano layout: "3 (the A key plays C 3)". In the Scale layout: "3 (the A key plays the scale's root note)". In Chord strips: "3 (chords in octave 3, bass notes in octave 2)". The same octave stays chosen. Before 0.9.11 every layout said "the A key plays C 3". In the lowest octave of Chord strips the choice reads "-2 (chords in octave -2, number keys play the lowest note)". Control+J says "Chord strips, C major. Octave -2, the chords play in octave -2, and the number keys play each chord's lowest note", then the velocity and the chords. A plays the C major chord very low. 1 plays its lowest note, C -2, on its own.

### Step Z.20: The octave on a drum kit

**What to check:** Add a drum kit track (Control+T, Instrument, a kit from the Drum Kits family). Choose octave 3 in the Keyboard menu's Octave submenu. Press Control+2, then press X, then Z, then Control+J. Choose octave 5 in the Octave submenu. Press A at each octave. Then select a piano track and press X and Z there.

**What to expect:** Choosing octave 3 says "Octave 3. The Drum layout does not use the octave". X says "Octave 4. The Drum layout does not use the octave", and Z says "Octave 3. The Drum layout does not use the octave". Control+J says "Drum layout. Octave 3. The Drum layout does not use the octave.", then the velocity. The Octave submenu and the Octave choice read, for example, "3 (the Drum layout does not use the octave)". Choosing octave 5 says "Octave 5. The Drum layout does not use the octave". A plays the kick at every octave. On the piano track, X and Z say just the octave, for example "Octave 6" and "Octave 5" after octave 5. Before 0.9.11 a drum kit's words said "the A key plays C 3".

### Step Z.21: Escape on the start screen

**What to check:** Close the project (Control+W). On the start screen, press Browse projects, then Escape. Open the Help menu button's menu, then press Escape. Press New project, then Escape in its window. Press Shift+Escape. If you use Magnifier, press Windows+Escape. Last, press Escape on its own, then start Musician Forge again.

**What to expect:** Escape in Browse projects, in the Help menu and in the New project window closes only that window, and you are back on the start screen. Shift+Escape does nothing. Windows+Escape is Windows' own shortcut (it closes Magnifier), and Musician Forge stays open. Escape on its own closes Musician Forge, as the Quit button does. Before 0.9.11 Escape did nothing on the start screen.

### Step Z.22: The reverb's settings while the song plays

**What to check:** Add a Reverb with the Hall preset to a track that plays long chords (a Spark Pad region, say), and play the song. Open the reverb's settings (Control+F, then Enter on it). While the song plays, arrow up and down quickly in Decay time in seconds, then in Brightness in percent, Pre-delay in milliseconds and Stereo width in percent. Then type a new Decay time.

**What to expect:** Each change is heard at once and smoothly, with no click, crackle or zipper sound, even when you arrow quickly. Decay, Brightness and Stereo width glide to the new setting in a fiftieth of a second. A new Pre-delay fades from the old one to the new one, with no bend in the pitch. Before 0.9.11 these switched at once and could click.

### Step Z.23: Echoes and reverb ringing on after the music stops

**What to check:** Record a short chord at bar 1 on a piano track. Add a Delay with the Dub echo preset to that track and open its settings (Control+F, then Enter on it). Press Alt+P to play, and Alt+P again just after the chord. While the echoes still sound, go to Feedback in percent (how many echoes) and press Home (0). Then press OK, remove the delay (Delete in Effects), add a Reverb with the Cathedral preset and open its settings. Play and stop the same way, and a few seconds later, while it still rings, set Decay time in seconds to 1.

**What to expect:** The echoes are not cut off: the echo already on its way comes once more, then the echoes stop. The cathedral's ringing fades out quickly and smoothly. Before 0.9.11 both stopped dead the moment you turned them down.

### Step Z.24: Adding things at the end of the song

**What to check:** On a drummer track whose region fills the song, turn on All sections and let the song play to its end ("End of song, stopped. Bar 9, beat 1"). Open Tempo changes (Control+Shift+T), press Alt+A, listen to the bar and press Escape. Do the same in Time signature changes (Control+Shift+M), Key changes (Control+Shift+K), the Chord track (Control+Shift+H), an automation lane's points (Control+Shift+U, then Enter on a lane; if there is none, Alt+A and Volume add one) and the Event list (Control+L). Press Control+G and listen to the bar. Then press P in the Regions list on the drummer's region.

**What to expect:** Every Add window, and Go to bar, starts at bar 8, the last bar, where what you add is heard. The playhead stays at the end. P says "There is no empty stretch at the end of the song. Add a section first.". Where the bars before the end are empty, P fills them instead. With a drummer region in bars 1 and 2 only, for example, P says "Added a rhythm player region on Anvil (drums), bars 3 to 8: Anvil, drums, Rock, variation 1 of 6".

### Step Z.25: The song's new length

**What to check:** With the song played to its end as in Step Z.24, copy the drummer's 8-bar region (Control+C in the Regions list) and paste it (Control+V). Press Control+Z. Import an audio file of about 3 seconds (Control+Shift+I). Press Control+Z. Then make the drummer's region play 2 times (Alt+Enter, Plays this many times in a row: 2) and press Control+D on it.

**What to expect:** Paste says "Pasted 1 region at Bar 9, beat 1. The song is now 16 bars long.": the region goes after the last bar, and the last section grows to hold it. Import says the same at its end, for example "Imported Idea.wav on the new track Idea, 3 seconds, at Bar 9, beat 1. The song is now 10 bars long." Each Control+Z puts the song back to 8 bars. Playing 2 times ends "loops 2 times, to bar 17. The song is now 16 bars long.", and Duplicate says "Duplicated 1 region, starting at Bar 17, beat 1. The song is now 32 bars long." Adding or copying a section, or making one longer with F2 in Sections, says it too: in an 8-bar song, Alt+A in Sections says "Added Section 2: bars 9 to 16, 8 bars. The song is now 16 bars long." An edit that does not make the song longer says nothing more. Before 0.9.11 nothing said that the song had grown.

### Step Z.26: A drummer builds where a loop is cut

**What to check:** Open Sections and make Section 1 16 bars long (F2). Add Anvil with the style Rock on a new track (Control+Shift+R), with How long set to "Bars I choose", from bar 1 to bar 4. Select the drummer's track and press Control+Shift+R again: Rock, Where "On the selected track", bars 11 to 14. In the Regions list, press Enter on this second region and set its Intensity to 100. Then press Alt+Enter on the first region, tick "Loop until the next region (or the end of the song)" and press Enter. Turn on All sections and play from bar 7.

**What to expect:** The first region's line ends "loops until the next region, 3 times, to bar 11": it plays twice, then bars 9 and 10, the first half of a third time. In bars 9 and 10 the hi-hat builds into the louder drummer: closed, then half open, then wide open into bar 11, as a drummer region that ends at bar 11 would. Before 0.9.11 the build was cut off with the rest of the repeat, so there was none. Turn into notes (Enter on the first region, the Turn into notes button, then Yes) writes the build out as it is heard.

### Step Z.27: A bass leads in where a loop is cut

**What to check:** In the Chord track (Control+Shift+H), add C major at bar 1 and A minor at bar 4 (Alt+A for each). Add Bellows with the style Walking on a new track, How long "Bars I choose", bars 1 to 2. Select its track and add Bellows, Walking again, Where "On the selected track", bars 4 to 7. Press Enter on this second region and set its Complexity to 80. Press Alt+Enter on the first region, tick "Loop until the next region (or the end of the song)" and press Enter. Play from bar 2.

**What to expect:** The first region's line ends "loops until the next region, 2 times, to bar 4": it plays bars 1 and 2, then bar 3, the first half of its second time. Bar 3's last note now leads into the A minor at bar 4 (a G, a step below A), as a region that ends at bar 4 would, and nothing of the loop sounds on into bar 4. Before 0.9.11 bar 3 played the loop's first bar unchanged, ending on the A sharp that leads back to C. Keys, synth and guitar players lead in the same way.

### Step Z.28: A loop says where it now plays to

**What to check:** On one track, record a 2-bar part in bars 1 and 2, and a short part in bar 5 (press R again before bar 6). Name the first region Riff (F2). Press Alt+Enter on Riff, tick "Loop until the next region (or the end of the song)" and press Enter. Arrow to the second region, press Delete, then Yes. Press Control+Z. Press Alt+Right on the second region, then Alt+Left (the nudge step is a quarter note). Move it to bar 7 with the Region group's Move region button. Copy it (Control+C), go to bar 3, beat 2 (Control+G), and paste (Control+V). Arrow to Riff.

**What to expect:** Riff's line ends "loops until the next region, 2 times, to bar 5". Delete says "Deleted 1 region. Riff now loops to bar 9", the end of the song. Alt+Right says "Bar 5 beat 2. Riff now loops to bar 5 beat 2", and Alt+Left says "Bar 5. Riff now loops to bar 5". Move region says "Moved 1 region to Bar 7, beat 1. Riff now loops to bar 7". Paste says "Pasted 1 region at Bar 3, beat 2. Riff now loops to bar 3 beat 2". Riff's line now ends "loops until the next region, 2 times, to bar 3 beat 2": where a loop stops inside a bar, the line says the bar and the beat. Before 0.9.11 nothing said where the loop went, and the line said the next bar ("to bar 4"). Mute, Split, Join and Control+Z say nothing more.

### Step Z.29: Split and Join on a looping region

**What to check:** Record a 2-bar part in bars 1 and 2, name its region Riff (F2), and make it play 4 times (Alt+Enter, Plays this many times in a row: 4). Go to bar 2 (Control+G), press S in the Regions list, arrow through the list and play. Turn on Select (Shift+F8), press Space on the second and third regions, and press J. Press Control+Z twice and turn Select off (Shift+F8). Go to bar 6 and press S again.

**What to expect:** At bar 2, S says "Split at Bar 2, beat 1. 2. Riff, Section 1: starts at bar 2, ends at bar 3, 1 bar long, 4 notes. The loop carries on from bar 3" (with your number of notes). The list has Riff in bar 1, Riff in bar 2, and Riff from bar 3, which "loops 3 times, to bar 9". You hear the riff 4 times, as before. J says "Joined. 2. Riff, Section 1: starts at bar 2, ends at bar 9, 7 bars long", the notes, and "The loop is written out as notes, so it sounds as it did". At bar 6, S says "Split at Bar 6, beat 1. 2. Riff, Section 1: starts at bar 6, ends at bar 7, 1 bar long", the notes, and "The loop carries on from bar 7". The first region's line then ends "loops 3 times, to bar 6". Before 0.9.11, a split in the repeats said "Move the playhead inside the region to split it there", and a split in the first time made the repeats go silent. Each is one Control+Z.

### Step Z.30: A looping recording and section edits

**What to check:** Open Sections, make Section 1 4 bars long (F2) and press Alt+A (Section 2, bars 5 to 12). With the playhead at bar 1, import an audio file of about 3 seconds (Control+Shift+I) and make it play 4 times (Alt+Enter). In Sections, select Section 1 and press Alt+A. Turn on All sections and play from bar 3. Press Control+Z. Delete Section 2 (Delete, then Yes) and play. Press Control+Z. Select Section 1 and press Control+D. Press Control+Z. If you have a microphone, make the recording play 8 times and record over bars 5 and 6 on the same track.

**What to expect:** For a 3-second file, the recording's line ends "loops 4 times, to bar 7". Alt+A says "Added Section 2: bars 5 to 12, 8 bars. The song is now 20 bars long. The looping recording is cut into pieces, so it sounds as it did". The recording plays as before to the end of bar 4, the new section is silent for it, and at bar 13 it carries on exactly where it left off, in time with the music. Deleting Section 2 says "Deleted Section 2. The looping recording is cut into pieces, so it sounds as it did". The recording now stops at the end of bar 4. Control+D says "Copied to Section 3: bars 13 to 16, 4 bars. The song is now 16 bars long. The looping recording is cut into pieces, so it sounds as it did", and the copy holds what the loop plays in bars 1 to 4. After the take the same words come, and the recording carries on after it, from bar 7. Before 0.9.11 the recording played straight on through a new section, and the bars after a newer take went silent. Each change is one Control+Z.

### Step Z.31: Moved and copied regions keep their feel

**What to check:** Use headphones. Make Section 1 12 bars long (Sections, F2). Add a rock drummer with How long "Bars I choose", bars 1 to 4, and play it. Move it to bar 5 (the Region group's Move region button) and play it again. Copy it (Control+C), go to bar 9 (Control+G), paste (Control+V) and play the copy. Then add a rock drummer on a new track at bars 2 to 3 and make it play 4 times (Alt+Enter). On its track, record a few notes in bars 6 and 7 (Control+G to bar 6, R, play, then R in bar 7), and listen to bars 8 and 9.

**What to expect:** The moved region and the copy sound exactly as the region did where it was, down to the drummer's small pushes and pulls in time. The recording says "The recording replaced the rhythm player in bars 6 to 7. Control+Z brings it back". Bars 8 and 9 then play exactly what the loop played there, and their region is still a rhythm player. Before 0.9.11 each of these played a feel of its own, with notes up to about 15 thousandths of a second off, so it sounded a little different. Listen closely: the difference is small. Reforge still gives a region a new performance, with a new feel.

### Step Z.32: Pitch correction on a trimmed recording

**What to check:** On an audio track, record yourself holding one steady note, an E flat, from bar 1 to the end of bar 4: sing it, or play it into the microphone. Add a key change to E flat major at bar 3 (Control+Shift+K, Alt+A). Add Pitch correction with the Robotic preset to the audio track (Control+F, Alt+A). In the Regions list, press Alt+Enter on the recording, set Starts at bar to 2 and press Enter. Play from bar 2.

**What to expect:** You hear "Trimmed", then the recording's line. In bar 2, where the song is still in C major, your E flat is pulled onto a note of C major (D or E). From bar 3, where the key changes, it is your own E flat. Before 0.9.11, a recording trimmed at its start changed key too early, by as much as was trimmed off: here at bar 2, a bar early. A recording saved before this change plays exactly as it did until you change it (trim it, move it, or change the track's pitch correction).

### Step Z.33: The foot in other time signatures

**What to check:** Add a rock drummer and, in its Kit pieces, press Space on the Hi-hat pedal, and play. Then set the time signature to 3/4 (Control+Shift+M), read the Hi-hat pedal's line in Kit pieces and play. Do the same in 6/8, in 3/8 and in 2/8.

**What to expect:** Space says "Hi-hat pedal: on, the foot on two and four". In 3/4 the line reads "Hi-hat pedal: on, the foot on two and three", in 6/8 "Hi-hat pedal: on, the foot on two" (the second of the bar's two beats), and in 3/8 "Hi-hat pedal: on, the foot on two and three", with the foot on the second and third eighths. You hear the foot where the line says. In 2/8 the line reads "Hi-hat pedal: on, the foot rests in 2/8", and the foot does not play. Before 0.9.11 the line said "the foot on two and four" whatever the time signature, and in 3/8 the foot did not play.

### Step Z.34: Short notes through Fuzz

**What to check:** On a piano track, add a Distortion with the Fuzz preset (Control+F, Alt+A). Record a few short notes with rests between them and play them back. Then choose the Dubstep growl preset and play again. Last, remove the Distortion, add an EQ with the Bass boost preset and play once more.

**What to expect:** Each note ends cleanly, with no click as it stops, and the next note starts cleanly, with nothing left over from the note before. Before 0.9.11, while the song played, a note that ended quickly through these could end with a click. This is while playing: exports are unchanged by it.

### Step Z.35: Join with one region muted

**What to check:** On one track, record a short part in bar 1 and another in bar 2, and name their regions Riff 1 and Riff 2 (F2 in the Regions list). Press M on Riff 2. Turn on Select (Shift+F8), press Space on both regions and press J. Then press M, and press J again.

**What to expect:** The first J says "Riff 2 is muted and Riff 1 is not. Mute or unmute them so they match, then join.", and nothing changes: both regions stay selected. M then mutes both ("Muted 2 regions"), and J joins them into one region, still muted. When the two regions have the same name, as after a split, the words say where each starts, for example "Riff at bar 2 is muted and Riff at bar 1 is not. Mute or unmute them so they match, then join." Before 0.9.11 the joined region took the first region's setting, so a muted part could start playing, or a part you heard could go quiet.

### Step Z.36: Said once

**What to check:** Open Automation (Control+Shift+U) on a track with a Volume lane and press Space on the lane, then press the Turn lane on or off button. Press Enter on the lane, add a point with Alt+A and press OK, then press Enter on it, change its value and press OK. In the Chord track (Control+Shift+H), add a chord change with Alt+A and press OK, then press Enter on it and press OK. In Chord strips (Control+Shift+J), press the Change chord button, choose another chord and press OK. In Effects (Control+F), press the Turn on or off button. Last, open a reverb's settings and arrow Decay time in seconds down to 1.

**What to expect:** After each, the line you are on is read once, with its new words, for example "Volume: 1 point, off (the track's own setting is used)", "Bar 2, beat 1: volume 60, stays there to the end", "Bar 3, beat 1: D minor", "A: D minor" or "1. Reverb, Medium room, off". Decay time says "1 second". Before 0.9.11 each of these lines was said twice, and a number box said "1 seconds".

## New in 0.9.10

### Step Y.1: A kick under every crash

**What to check:** Add a rock drummer (Anvil, Rock) and set its Fill amount to 100 in its editor. In its Kit pieces, press Space on the Kick ("Kick off") and play the region from its start. Then press Enter on Crash cymbals, set When a crash comes to Never, and play it again.

**What to expect:** With the Kick off the groove plays no kicks, but where the region starts and after every fill the kick still lands with the crash, as a drummer's foot does. With Never there is no crash there, and no kick with it. Each change is one Control+Z.

### Step Y.2: Following a strummed guitar

**What to check:** Add Hammer (guitar) with the style Rock strum, then Bellows (bass) on a track of its own. In the bass's editor, set Follow to Another track and Track to follow to the guitar's track. Play.

**What to expect:** The bass lands with each strum, on the beat, instead of stuttering through the strum's six strings.

### Step Y.3: Duplicating a looping region

**What to check:** In the Regions list, press Alt+Enter on a region and make it play 4 times. Press Control+D (Duplicate) and arrow through the Regions list.

**What to expect:** The copy starts after the last repeat, and the first region's line still says "loops 4 times, to bar ...".

### Step Y.4: Moves that cannot be made

**What to check:** In the Regions list, press the Region group's Move region button and type bar 1, beat 9. Then open Tempo changes (Song group), add changes at bar 5 and bar 9, edit the one at bar 9 and give it bar 5, beat 1.

**What to expect:** Move region says "Bar 1 has 4 beats, so the beat must be from 1 to 4", and the window stays open with what you typed, so you can put it right. The tempo change is not moved: it says "Another tempo change is already at bar 5, beat 1, so this one was not moved. Choose another beat, or edit that one instead", and the window stays open. Nothing is lost.

## New in 0.9.9

### Step X.1: Changing the style keeps one cymbal keeping time

**What to check:** Add a jazz drummer. In its Kit pieces, open the Ride's settings (Enter) and choose eighth notes in its Pattern list, then close the window. Change the region's Style to Rock and listen to the Kit pieces list. Press Control+Z.

**What to expect:** After the style change you hear "Hi-hat off", and the Hi-hat line reads "Hi-hat: off, the ride keeps time": the ride keeps time, and the hi-hat does not play over it. Control+Z brings back the jazz drummer as it was.

### Step X.2: A piece that is on always plays

**What to check:** In a jazz drummer's Kit pieces, press Space on the Hi-hat. In a house drummer's Kit pieces, press Space on the Snare, the Toms and the Ride. Read the list.

Then add a metal drummer, choose variation 3, and press Space on its Hi-hat, then Space again.

**What to expect:** No line says "not in this groove": a piece that is off just says "off". The jazz Hi-hat says "Hi-hat on with eighth notes, ride off", and you hear eighth notes on the hi-hat. Each house piece turned on plays the first of its patterns and its line says "on, pattern changed". In metal variation 3, where the crash keeps time, the Hi-hat says "Hi-hat on with eighth notes, crash off" and takes over (the crash still plays where the region starts and after fills); Space again says "Hi-hat off, crash on". Each change is one Control+Z.

### Step X.3: An older project still sounds the same

**What to check:** Open a project saved with 0.9.7 or earlier that has a drummer, especially one where you set the open hi-hat's loudness in Track settings or made hand-made steps for the hi-hats, and play it.

**What to expect:** It sounds exactly as it did in 0.9.7: the open hi-hats at their own loudness, and hand-made hi-hat steps in their places.

## New in 0.9.8

### Step W.1: The ride and the hi-hat take turns

**What to check:** In a rock drummer's Kit pieces, arrow to Ride and press Space, and play. Press Space on the Ride again. Press Space on the Ride once more, so it is on, then arrow to Hi-hat and press Space, and Space on Hi-hat once more. Press Control+Z five times, so the Hi-hat is on and the Ride off as at the start. Then open the Ride's settings (Enter), tick and untick Play this piece, tick it again, and tick the check box under it, "Play the hi-hat". Try a jazz drummer and a house drummer too.

**What to expect:** Space on the Ride says "Ride on with the hi-hat's rhythm, hi-hat off": the ride keeps time with the hi-hat's rhythm, and the Hi-hat line in the list reads "Hi-hat: off, the ride keeps time". Space again says "Ride off, hi-hat on", and the Hi-hat is back on. Space a third time says "Ride on, hi-hat off" (the ride has its rhythm now). Space on the Hi-hat says "Hi-hat on, ride off", and the Ride's line reads "Ride: off, the hi-hat keeps time"; Space on it again says "Hi-hat off, ride on", because the Hi-hat had turned the Ride off. In the Ride's window, ticking Play this piece says "Ride on with the hi-hat's rhythm, hi-hat off", unticking it says "Ride off, hi-hat on", and ticking it again says "Ride on, hi-hat off"; right under it is "Play the hi-hat (the ride and the hi-hat take turns)", which unticks itself when the ride goes on and ticks itself again when the ride goes off, and ticking it yourself while the ride is on turns the ride off ("Hi-hat on, ride off"). The Hi-hat's window has "Play the ride" the same way. A piece you turned off yourself stays off: the other one going on and off again does not bring it back. In jazz the Ride is on from the start and the Hi-hat off ("Hi-hat: off", since the jazz grooves keep time on the ride), so Space on the Ride only turns it off and on, and the Hi-hat pedal keeps the foot going. Space on the jazz Hi-hat turns it on with eighth notes and turns the Ride off ("Hi-hat on with eighth notes, ride off"). A house drummer's Ride and Hi-hat windows have no second check box, since those two do not take turns there: on house, trap or dubstep, Space on the Ride just turns it on and the Hi-hat keeps playing. The Hi-hat pedal never changes with any of these: in jazz, funk and pop it stays on and keeps the foot going under the ride; in rock, hard rock, metal and the drum machines it stays off until you turn it on. Each change is one Control+Z.

### Step W.2: The Hi-hat pedal is its own piece

**What to check:** In a jazz drummer's Kit pieces, arrow to Hi-hat pedal and listen to its line. Press Space on it, then Space again. Turn the Ride on and off. Then look at a rock drummer's Hi-hat pedal, a funk drummer's and a house drummer's, and open the pedal's settings with Enter.

**What to expect:** The list has Hi-hat (the hand, closed and open sounds) and, right after it, Hi-hat pedal (the foot); there is no separate piece for the open sound any more, and the Hi-hat is simply on or off. In jazz the pedal's line reads "Hi-hat pedal: on" (the groove has the foot in it); in funk and pop it reads "Hi-hat pedal: on, the foot on two and four". Space turns it off (the line reads "Hi-hat pedal: off" in jazz, "Hi-hat pedal: off" in funk and pop too) and the foot stops; Space again turns it back on. The Ride going on and off leaves the pedal as it was. In rock, hard rock, metal, house, trap and dubstep the pedal's line reads "Hi-hat pedal: off" until you turn it on; then it reads "Hi-hat pedal: on, the foot on two and four" and plays that. The pedal's window has Play this piece, Pattern (the foot on two and four, on every beat, or on one and three), Complexity and Step pattern, and nothing about how open the hi-hat is (that is the Hi-hat's). Each change is one Control+Z.

## New in 0.9.7

### Step V.1: A new project starts with no tracks

**What to check:** On the start screen, choose New project, give it a title and press Enter. When the New track list opens, press Escape.

**What to expect:** The New track list opens by itself once the project window shows. Its list is called "Kind of track" and starts on Instrument. After Escape the project has no tracks: the Tracks list reads "No tracks yet. Press Control+T to add one."

### Step V.2: Getting around with no tracks

**What to check:** In the empty project, press F6 a few times, press R, play a few letter keys on the Musical keyboard (Control+2), and press Track settings, Effects and Delete track.

**What to expect:** Nothing crashes. R, the letter keys and those buttons say "There is no track yet. Press Control+T to add one." (the letter keys say it once, not on every key). Space still plays and stops, and the Song group's buttons still open.

### Step V.3: New track: Instrument, Audio, Import file

**What to check:** Press Control+T, press Enter on Instrument, choose Grand Piano and press Enter. Then Tab to the New track button, press Space, arrow to Audio and press Enter. Open the list once more, choose Import file and pick a short WAV or MP3 file.

**What to expect:** Each makes a new track: "Added 1. Grand Piano", then the audio track, then a track named after the imported file ("Imported ... on the new track ..."). Escape or Cancel in any of these windows adds nothing.

### Step V.4: New track: Rhythm player

**What to check:** Press Control+T, arrow to Rhythm player and press Enter. Choose Anvil, a rock style, and press Enter.

**What to expect:** The New rhythm player window offers only "On a new track", and a new drummer track with its region appears. Control+Shift+R still offers the selected track too.

### Step V.5: Kit-piece loudness in Track settings

**What to check:** On the drummer's track, press Track settings (or Alt+Enter on the track). Tab past Mute and Solo to the kit sliders. Move Kick loudness to 0 and Ride loudness up, press Enter and play. Then open a project made with 0.9.6 that has a drummer, play it, and open its drummer track's Track settings.

**What to expect:** Ten sliders, one for each kit piece (Hi-hat and Hi-hat pedal among them), each at 50. With Kick at 0 no kick plays at all, fills included. Control+Z takes it back in one step. The 0.9.6 project has the sliders too, all at 50, and sounds exactly as it did.

### Step V.6: Enter on a kit piece

**What to check:** Press Enter on the drummer's region in the Regions list. Tab to Kit pieces, arrow to Kick and press Enter. Press Escape. Try the same with an electronic drummer (house or trap).

**What to expect:** Enter opens the Kick's window, for every drummer. It has no Loudness slider (that is in Track settings now), unless the region comes from an older project that set the piece's own loudness. Escape goes back to Kit pieces.

### Step V.7: The ride and the hi-hat take turns

**What to check:** In a rock drummer's Kit pieces, arrow to Ride and press Space, and play. Press Space on the Ride again.

**What to expect:** The ride and the hi-hat take turns, as Step W.1 says in full (changed in 0.9.8: the hi-hat is one piece, with the pedal as a piece of its own; see Step W.2). Each change is one Control+Z.

### Step V.8: Steps turn a piece back on

**What to check:** Turn the Kick off with Space. Press Enter on it, open Step pattern (Alt+S), arrow to step 2 and press Space. Press Escape twice.

**What to expect:** The step turns on, and it says the Kick is hand-made now and "Kick on". The Kit pieces list then reads "Kick: on, hand-made".

### Step V.9: Enter in the lists

**What to check:** Press Enter in each of these: Tempo changes, Time signature changes, Key changes, the Event list (on a note), Recordings (on a recording), Sections, the Chord track, Effects, and Automation (then Enter again on a point). Then try Alt+Enter in one of them.

**What to expect:** Enter opens the edit window for the line you are on (in Sections it goes to that section). Alt+Enter does not.

### Step V.10: Buttons are no longer cut off

**What to check:** Tab to the Metronome check box and press Space. Press Control+K. Press the Go to start, Forward and Stop buttons. Press F6 twice quickly.

**What to expect:** You hear "Metronome check box checked" with nothing cutting it off, and no window title read after it. Control+K says "Metronome on". After each button its result comes a moment later, after the button's name, not over it. F6 twice says only the area you land on. If the window title or the whole window is ever read after a button, please note which button.

### Step V.11: Edit windows keep what you typed

**What to check:** In Tempo changes, press Enter, type 12o as the tempo and press Enter.

**What to expect:** It says what is wrong, and the same window comes back with everything you typed still in it, so you only fix the one mistake.

### Step V.12: F2, the Select buttons and the start screen's buttons

**What to check:** In the Regions list press F2 on a region, type a name and press Enter. Tab to the Edit group and press Select or unselect, then Select all. Then press Control+W, and on the start screen Tab past Recent projects to Open and Remove from list.

**What to expect:** F2 renames the region, not the track. Select all selects every track (or every region, if the Regions list was the last one you were in). Open opens the project; Remove from list takes it off the list (the file is kept) and says so.

### Step V.13: Holding keys, and a stuck note

**What to check:** Hold Space for two seconds. Hold B on the Musical keyboard. Then hold a letter key, press Alt, release the key, and press Escape twice.

**What to expect:** Holding Space plays (or stops) once; holding B changes the layout once. The held note stops when the menu opens or at the latest with Escape, and the key plays again afterwards.

### Step V.14: Sliders and volume

**What to check:** In Track settings, Tab to Volume and press Up arrow, then Page Up. Then set a track's volume to 0 and play: listen for its reverb. Export a song whose first note is at bar 1, beat 1.

**What to expect:** Up and Page Up raise the volume (please tell us if they lower it). A track at volume 0 is completely silent, reverb included, and its reverb fades with it. The export's first note is no louder than the rest.

### Step V.15: Quantize in 7/8

**What to check:** Make a project in 7/8 and record a few notes slightly off the beat, one just before the end of bar 1. In the Regions list press Quantize, choose Quarter note and press Enter.

**What to expect:** Every note in the region moves, the last one to the start of the next bar if that is nearer, and it says how many notes it quantized.

### Step V.16: An older project sounds the same

**What to check:** Open one of your projects made with 0.9.6 or earlier and play it all the way through.

**What to expect:** The rhythm players play the same notes as before, except that the drummer's ride and hi-hat now stop for each fill (Step V.17). Apart from that, only the reverb is a little drier on tracks below full volume, because the reverb now follows each track's volume.

### Step V.17: Fills take both hands

**What to check:** Add a rock drummer, turn its Ride on (Space in Kit pieces), set Fills to 100 and play. Try metal and jazz too, and a rock drummer with the ride off.

**What to expect:** In each fill, the ride (or the hi-hat) stops when the fill starts, and comes back with the crash on the next bar; only the kick and, where it is on, the Hi-hat pedal keep playing under the fill. No fill has a cymbal ticking along on top of the toms.

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

**What to expect:** The Clap or rim, Toms ("off, in fills only"), Crash cymbals, Ride, Congas and bongos, and Shaker, tambourine, cowbell and claves say "off" (not in the groove), yet the fills still use the toms and the region still starts with a crash. With the Kick off, the groove's kicks stop and the fills' kicks stay.

### Step N.5: Fast hi-hats

**What to check:** Set the tempo to 180 and the Hi-hat's pattern to sixteenth notes, then to disco sixteenths.

**What to expect:** Both stay sixteenth notes. (The ride still plays eighth notes above 120 beats a minute.)

### Step N.6: The button groups are back

**What to check:** Tab through the Transport, Track, Edit, Region and Song groups, then open the menus. Try their shortcuts: Control+T, Control+Z, Control+Shift+R and the rest.

**What to expect:** The groups' commands are buttons again and no longer in the menus, and their shortcuts still work.

### Step N.7: Commas in the Menus group

**What to check:** Tab to the Menus group and open a menu with its button.

**What to expect:** Each item is read with a comma before its shortcut, for example "Add a section after this one, Control+Shift+N".

## Added in 0.9.4 and 0.9.5

### Step E.1: Selecting notes in the event list

**What to check:** Press Enter on a region of notes to open its event list (Control+L opens the whole track's), press Space on two notes, then Control+Up. Then press Alt+Q (Quantize).

**What to expect:** Both notes move. Quantize offers Selected notes, Whole track or All tracks.

### Step E.2: Exporting tracks on their own

**What to check:** Export audio (Control+E) with WAV and What to export "Only the tracks you choose". Press Space on one track and export it; then choose two.

**What to expect:** One WAV file for one track; a zip with one file for each of the two.

### Step E.3: MIDI in another program

**What to check:** Export MIDI (Control+Shift+E) and import the file into another program.

**What to expect:** The instruments (guitar, drums), the tempo, time signature and key are right, and the Chord track is there and silent.

### Step E.4: A kit without a sound

**What to check:** Set a rock drummer's Crash cymbals to the splash (Which cymbal), then change its Patch to the Forge Trap Kit, which has no splash.

**What to expect:** The splash plays on the crash; it does not go silent.

### Step E.5: Fills and Complexity

**What to check:** In a jazz drummer's region (the jazz grooves keep time on the ride), set Fill amount to 100 and move Fill complexity high and low. Open the Ride's settings and move its Complexity to 100 and to 0. Reforge a few times.

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

**What to check:** Open the Hi-hat's settings.

**What to expect:** There is no "Play this rhythm on" any more: each piece plays only its own sounds (the Hi-hat its closed and open sounds; the foot is the Hi-hat pedal, a piece of its own).

### Step E.10: The ride in fast songs

**What to check:** In a jazz drummer's region, open the Ride's settings and look through the Pattern list. Then set the song's tempo to 130, look again, and play the region.

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

## Known limits in 0.9.11

- Musician Forge needs Python until the 1.0 installer.
- The guitar packs play from B0 to D5 (key 35 to 86, with middle C as C3): drop D, drop C and B standard work; lower notes are silent.
- Rhythm players following a recording work best with clear, separate hits (picked or strummed guitar, piano, drums); slow pads and legato lines have few clear starts.
- In the Step pattern, a step can hold several sounds, but Left and Right keep only one of them (Control+Z brings the others back).
- Low-latency hearing yourself needs Windows 10 or later and a sound driver that offers it; Musician Forge says when it does not.
- Hearing yourself through a computer always takes a moment. For none at all, use direct monitoring on a USB microphone or audio interface.
- Bluetooth headphones add a delay you can hear when playing live.
