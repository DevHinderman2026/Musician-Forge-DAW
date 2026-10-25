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

To update to a newer test version, put its files in the same folder and run "Install or Update Musician Forge" again. Your projects are kept (they are in Documents, Musician Forge Songs).

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

**What to check:** Fill the chord track with chords at bars 1 and 2 only. Add a Spark Pad region over bars 1 and 2 and, with Alt+Enter, make it play 4 times. In the Tracks list, on the pad's track, press Control+G and go to bar 5, press R, play a few notes and press R again in bar 6. Then add a 2-bar drummer region that plays 8 times, open Sections (Song group), select Section 1 and press Alt+A. Last, press Enter on a looping player region and choose Turn into notes.

**What to expect:** Your notes replace bars 5 and 6, and the pad carries on in bars 7 and 8 exactly as the loop played; since the chord track has no chords there, it is written out as notes, and Musician Forge says "The loop carries on after the recording as notes, so it sounds as it did". The drummer's loop keeps playing on both sides of the new section and stays a rhythm player. Turn into notes writes out every repeat you hear, as one longer region that no longer loops. Each of these is one Control+Z.

### Step Z.9: The drummer's foot and the percussion

**What to check:** Add a funk drummer, set its Intensity to 90 and play. Then add a rock drummer, turn on its Shaker, tambourine, cowbell and claves with Space, set Fill amount to 100 and play. Last, add a pop drummer and play.

**What to expect:** In funk the hi-hat opens on two and four and the Hi-hat pedal waits there, so the open hi-hat rings instead of being cut off by the foot. The rock tambourine plays every one of its notes, through the fills too, as if a second player had it. The pop drummer's own tambourine on two and four is heard now.

### Step Z.10: The Ride in metal variations 3 and 4

**What to check:** Add a metal drummer and choose variation 3. In its Kit pieces, press Space on the Ride, then Space on the Ride again. Then press Space on the Hi-hat, Space on the Ride, Space on the Ride again, and Space on the Hi-hat again.

**What to expect:** Space on the Ride says "Ride on with eighth notes, crash off", and the Crash cymbals line reads "Crash cymbals: off, the ride keeps time"; Space again says "Ride off, crash on". With the Hi-hat on first, the Ride says "Ride on with the hi-hat's rhythm, hi-hat off", then "Ride off, hi-hat on", and turning the Hi-hat off says "Hi-hat off, crash on". One cymbal always keeps time, and each change is one Control+Z.

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

**What to expect:** Move region says "Bar 1 has 4 beats, so the beat must be from 1 to 4", and the window stays open with what you typed, so you can put it right. The tempo change is not moved: it says "Another tempo change is already at bar 5, beat 1, so this one was not moved", and the window stays open. Nothing is lost.

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
