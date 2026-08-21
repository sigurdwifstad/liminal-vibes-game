# End game levels plan

## Level 9: Give the monster a hug
- The monster is now friendly and will not chase the player.
- The monster stands still at the end of a long hallway with no exit door.
- When the player is halfway to the monster, the audio file `monster_hug.wav` plays
- The player advances to the level 10 by touching the monster.

## Level 10: The final level
- The player has now become the monster and is now chasing a new child character.
- The player-monster is as tall as the monster. The screen border is now decorated with red veins, and the player-monster has a red tint to their vision.
- The monster_footstep sound effect plays when the player-monster moves, not the regular footstep sound effect.
- The new character is a small child who runs away from the player, with animated legs and arms.
- The child has blue torso and arms, brown legs, and a beige head with a small brown hair tuft on top (not using noisy textures).
- The spider monster is no longer present in this level.
- The player-monster cannot sprint. The stamina bar is replaced by the text "Press SHIFT to teleport" ONLY when out of sight of the child.
- When the player-monster presses `Shift` and is out of sight of the child, they teleport to a random location in the level and the monster_appearing sound effect plays.
- The child uses a simple pathfinding algorithm to explore the maze, and will try to run away from the player-monster when it is in sight.
- The child now uses local greedy step-by-step avoidance: at each decision point it only moves to a neighbor cell that's equal-or-farther from the player-monster, re-evaluating every frame while fleeing (or immediately when stuck), and freezes in place at genuine dead ends instead of being forced toward the player. 
- When the player-monster catches the child, the monster scream sound effect plays. Then, the game freezes, and fades to black with the text "END GAME" and the game ends, while playing the audio file `endgame.mp3`.
- The game stays at the END GAME screen until the player presses `R` to restart the game, or ESC to quit the game.