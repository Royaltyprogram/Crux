# IMO 2024 Problem 3 Solution

§1.3 IMO 2024/3, proposed by William Steinberg (AUS)
Available online at https://aops.com/community/p31206050.
Problem statement
Let a1, a2, a3, ... be an infinite sequence of positive integers, and let N be a positive
integer. Suppose that, for each n > N, the number an is equal to the number
of times an−1 appears in the list (a1,a2,...,an−1). Prove that at least one of the
sequences a1, a3, a5, ... and a2, a4, a6, ... is eventually periodic.
We present the solution from “gigamilkmen’tgeg” in https://aops.com/community/
p31224483, with some adaptation from the first shortlist official solution as well. Set
M := max(a1,...,aN).
¶ Setup. We will visualize the entire process as follows. We draw a stack of towers
labeled 1, 2, ..., each initially empty. For i = 1,2,..., we imagine the term ai as adding
a block Bi to tower ai.
Then there are N initial blocks placed, colored red. The rest of the blocks are colored
yellow: if the last block Bi was added to a tower that then reaches height ai+1, the next
block Bi+1 is added to tower ai+1. We’ll say Bi contributes to the tower containing Bi+1.
In other words, the yellow blocks Bi for i > N are given coordinates Bi = (ai,ai+1)
for i > N. Note in particular that in towers M +1, M +2, ..., the blocks are all yellow.
28
24
18
26 14
22 10
20
16
12
9 13 17 23 27
N 21 11 15 19 25
1 2 3 4 5 6 7 8 9
M
We let h denote the height of the (cid:96)th tower at a given time n. (This is an abuse of
(cid:96)
notation and we should write h (n) at time n, but n will always be clear from context.)
(cid:96)
¶ Up to alternating up and down. We start with two independent easy observations:
the set of numbers that occur infinitely often is downwards closed, and consecutive terms
cannot both be huge.
6
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025
36
32
28
34 24
30 18
26 14
22 10
20
16
12
9 13 17 23 27 31 35
N 21 11 15 19 25 29 33
1 2 3 4 5 6 7 8 9 10 11
L M
Claim — If the (k +1)st tower grows arbitrarily high, so does tower k. In fact,
there exists a constant C such that h ≥ h −C at all times.
k k+1
Proof. Suppose Bn is a yellow block in tower k+1. Then with at most finitely many
exceptions, Bn−1 is a yellow block at height k+1, and the block Br right below Bn−1 is
also yellow; then Br+1 is in tower k. Hence, with at most finitely many exceptions, the
map
B (cid:55)→ B (cid:55)→ B (cid:55)→ B
n n−1 r r+1
provides an injective map taking each yellow block in tower k+1 to a yellow block in
tower k. (The figure above shows B32 → B31 → B19 → B20 as an example.)
Claim — If an > M then an+1 ≤ M.
Proof. Assume for contradiction there’s a first moment where an > M and an+1 > M,
meaning the block Bn was added to an all-yellow tower past M that has height exceeding
M. (This is the X’ed out region in the figure above.) In Bn’s tower, every (yellow)
block (including Bn) was contributed by a block placed in different towers at height
an > M. So before Bn, there were already an+1 > M towers of height more than M.
This contradicts minimality of n.
It follows that the set of indices with an ≤ M has arithmetic density at least half, so
certainly at least some of the numbers must occur infinitely often. Of the numbers in
{1,2,...,M}, define L such that towers 1 through L grow unbounded but towers L+1
through M do not. Then we can pick a larger threshold N(cid:48) > N such that
7
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025
• Towers 1 through L have height greater than (M,N);
• Towers L+1 through M will receive no further blocks;
• aN(cid:48) ≤ L.
After this threshold, the following statement is true:
Claim (Alternating small and big) — The terms aN(cid:48), aN(cid:48)+2, aN(cid:48)+4, ... are all at
most L while the terms aN(cid:48)+1, aN(cid:48)+3, aN(cid:48)+5, ... are all greater than M.
¶ Automaton for n ≡ N(cid:48) (mod 2). From now on we always assume n > N(cid:48). When
n ≡ N(cid:48) (mod 2), i.e., when an is small, we define the state
S(n) = (h ,h ,...,h ;a ).
1 2 L n
For example, in the figure below, we illustrate how
S(34) = (9,11;a = 1) −→ S(36) = (9,12;a = 2)
34 36
36
32
28
34 24
30 18
26 14
22 10
20
16
12
9 13 17 23 27 31 35
N 21 11 15 19 25 29 33
1 2 3 4 5 6 7 8 9 10 11
L M
The final element an simply reminds us which tower was most recently incremented.
At this point we can give a complete description of how to move from S(n) to S(n+2):
• The intermediate block Bn+1 is placed in the tower corresponding to the height
an+1 of Bn;
• That tower will have height an+2 equal to the number of towers with height at least
an+1; that is, it equals the cardinality of the set
{i: h ≥ h }
i an
8
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025
• We increment han+2 by 1 and update an.
For example, the illustrated S(34) → S(36) corresponds to the block B34 at height h1
in tower 1 giving the block B35 at height 2 in tower h1, then block B36 at height h2+1
being placed in tower 2.
¶ Pigeonhole periodicity argument. Because only the relative heights matter in the
automata above, if we instead define
T(n) = (h −h ,h −h ,...,h −h ;a ).
1 2 2 3 L−1 L n
then T(n+2) can be determined from just T(n).
So it would be sufficient to show T(n) only takes on finitely many values to show that
T(n) (and hence an) is eventually periodic.
Since we have the bound h ≤ h +C, we are done upon proving the following lower
k+1 k
bound:
Claim — For every 1 ≤ (cid:96) < L and n > N(cid:48), we have h ≤ h +C ·(L−1).
(cid:96) (cid:96)+1
Proof. Assume for contradiction that there is some moment n > N(cid:48) such that
h > h +C ·(L−1)
(cid:96) (cid:96)+1
and WLOG assume that h was just updated at the moment n. Together with h ≤
(cid:96) k+1
h +C for all k and triangle inequality, we conclude
k
min(h1,...,h(cid:96)) > q := max(h(cid:96)+1,...,hL).
We find that the blocks now in fact alternate between being placed among the first (cid:96)
towers and in towers with indices greater than q thereafter. Hence the heights h , ...,
(cid:96)+1
h never grow after this moment. This contradicts the definition of L.
L
Remark. Infact,itcanbeshownthattheperiodisactuallyexactlyL,meaningtheperiodic
part will be exactly a permutation of (1,2,...,L). For any L, it turns out there is indeed a
permutation achieving that periodic part.
9
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025
§2 Solutions to Day 2