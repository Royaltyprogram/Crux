# IMO 2024 Problem 5 Solution

§2.2 IMO 2024/5, proposed by Chu Cheuk Hei (HKG)
Available online at https://aops.com/community/p31218774.
Problem statement
Turbo the snail is in the top row of a grid with 2024 rows and 2023 columns and
wants to get to the bottom row. However, there are 2022 hidden monsters, one in
every row except the first and last, with no two monsters in the same column.
Turbo makes a series of attempts to go from the first row to the last row. On
each attempt, he chooses to start on any cell in the first row, then repeatedly moves
to an orthogonal neighbor. (He is allowed to return to a previously visited cell.) If
Turbo reaches a cell with a monster, his attempt ends and he is transported back to
the first row to start a new attempt. The monsters do not move between attempts,
and Turbo remembers whether or not each cell he has visited contains a monster. If
he reaches any cell in the last row, his attempt ends and Turbo wins.
Find the smallest integer n such that Turbo has a strategy which guarantees being
able to reach the bottom row in at most n attempts, regardless of how the monsters
are placed.
Surprisingly the answer is n = 3 for any grid size s×(s−1) when s ≥ 4. We prove this
in that generality.
¶ Proof that at least three attempts are needed. When Turbo first moves into the
second row, Turbo could encounter a monster M1 right away. Then on the next attempt,
Turbo must enter the third row in different column as M1, and again could encounter a
monster M2 right after doing so. This means no strategy can guarantee fewer than three
attempts.
¶ Strategy with three attempts. On the first attempt, we have Turbo walk through
the entire second row until he finds the monster M1 in it. Then we get two possible cases.
Case where M1 is not on the edge. In the first case, if that monster M1 is not on
the edge of the row, then Turbo can trace two paths below it as shown below. At least
one of these paths works, hence three attempts is sufficient.
Starting row
M
1
Goal row
Case where M1 is on the edge. WLOG, M1 is in the leftmost cell. Then Turbo
follows the green staircase pattern shown in the left figure below. If the staircase is free
12
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025
of monsters, then Turbo wins on the second attempt. Otherwise, if a monster M2 is
encountered on the staircase, Turbo has found a safe path to the left of M2; then Turbo
can use this to reach the column M1 is in, and escape from there. This is shown in purple
in the center and right figure (there are two slightly different cases depending on whether
M2 was encountered going east or south).
Starting row Starting row Starting row
M M M
1 1 1
M
2
M
2
Goal row Goal row Goal row
Thus the problem is solved in three attempts, as promised.
¶ Extended remark: all working strategies look similar to this. As far as we know, all
working strategies are variations of the above. In fact, we will try to give a description of
the space of possible strategies, although this needs a bit of notation.
Definition. For simplicity, we only use s even in the figures below. We define the happy
triangle as the following cells:
• All s−1 cells in the first row (which has no monsters).
• The center s−3 cells in the second row.
• The center s−5 cells in the third row.
• ...
• The center cell in the sth row.
2
For s = 12, the happy triangle is the region shaded in the thick border below.
Starting row
Goal row
13
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025
Definition. Given a cell, define a shoulder to be the cell directly northwest or northeast
of it. Hence there are two shoulders of cells outside the first and last column, and one
shoulder otherwise.
Then solutions roughly must distinguish between these two cases:
• Inside happy triangle: If the first monster M1 is found in the happy triangle,
(cid:70)
and there is a safe path found by Turbo to the two shoulders (marked in the
(cid:70)
figure), then one can finish in two more moves by considering the two paths from
that cut under the monster M1; one of them must work. This slightly generalizes
the easier case in the solution above (which focuses only on the case where M1 is
in the first row).
Starting row
⋆ ⋆
M
1
Goal row
• Outside happy triangle: Now suppose the first monster M1 is outside the happy
triangle. Of the two shoulders, take the one closer to the center (if in the center
column, either one works; if only one shoulder, use it). If there is a safe path to
that shoulder, then one can take a staircase pattern towards the center, as shown in
the figure. In that case, the choice of shoulder and position guarantees the staircase
reaches the bottom row, so that if no monster is along this path, the algorithm
ends. Otherwise, if one encounters a second monster along the staircase, then one
can use the third trial to cut under the monster M1.
Starting row Starting row
⋆ ⋆
M M
1 1
M
2
Goal row Goal row
We now prove the following proposition: in any valid strategy for Turbo, in the case
where Turbo first encounters a monster upon leaving the happy triangle, the second path
must outline the same staircase shape.
14
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025
The monsters pre-commit to choosing their pattern to be either a NW-SE diagonal or
NE-SW diagonal, with a single one-column gap; see figure below for an example. Note
that this forces any valid path for Turbo to pass through the particular gap.
Starting row
M
M
M
M
M
M
M
M
M
M
Goal row
We may assume without loss of generality that Turbo first encounters a monster M1
when Turbo first leaves the happy triangle, and that this forces an NW-SE configuration.
Starting row
(M)
(M)
(M)
M
1
X ♣
♣
♣
♣
♣
♣
M
2
Goal row
Then the following is true:
15
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025
Proposition
The strategy of Turbo on the second path must visit every cell in “slightly raised
diagonal” marked with ♣ in the figure above in order from top to bottom, until
it encounters a second Monster M2 (or reaches the bottom row and wins anyway).
It’s both okay and irrelevant if Turbo visits other cells above this diagonal, but the
marked cells must be visited from top to bottom in that order.
Proof. If Turbo tries to sidestep by visiting the cell southeast of M1 (marked X in the
Figure), then Turbo clearly cannot finish after this (for s large enough). Meanwhile,
suppose Turbo tries to “skip” one of the ♣, say in column C, then the gap could equally
well be in the column to the left of C. This proves the proposition.
Remark(Memoriesofsafecellsareimportant,notjustmonstercells). Hereisoneadditional
observation that one can deduce from this. We say a set S of revealed monsters is called
obviously winnable if, based on only the positions of the monsters (and not the moves or
algorithm that were used to obtain them), one can identify a guaranteed winning path
for Turbo using only S. For example, two monsters in adjacent columns which are not
diagonally adjacent is obviously winnable.
Then no strategy can guarantee obtaining an obviously winnable set in 2 moves (or even
k moves for any constant k, if s is large enough in terms of k). So any valid strategy must
also use the memory of identified safe cells that do not follow just from the revealed monster
positions.
16
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025