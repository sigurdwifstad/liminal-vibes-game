# End game levels plan

## Level 9: Give the monster a hug
- The monster is now friendly and will not chase the player.
- The monster stands still at the end of a long hallway with no exit door.
- When the player is halfway to the monster, the audio file `monster_hug.wav` plays
- The player advances to the level 10 by touching the monster.

## Level 10: The final level
- The player has now become the monster and is now chasing a new character.
- The player-monster is as tall as the monster and has two black arms extending into the field of view.
- The new character is a small child who runs away from the player, with animated legs and arms.
- The player-monster cannot sprint. The stamina bar is replaced by the text "Press SHIFT to teleport" ONLY when out of sight of the child.
- When the player-monster presses `Shift` and is out of sight of the child, they teleport to a random location in the level
- When the player-monster catches the child, the game freezes, and fades to black with the text "END GAME" and the game ends, while playing the audio file `endgame.wav`.