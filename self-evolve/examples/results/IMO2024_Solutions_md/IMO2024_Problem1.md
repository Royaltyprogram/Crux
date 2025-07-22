# IMO 2024 Problem 1 Solution

§1.1 IMO 2024/1, proposed by Santiago Rodriguez (COL)
Available online at https://aops.com/community/p31205921.
Problem statement
Find all real numbers α so that, for every positive integer n, the integer
(cid:98)α(cid:99)+(cid:98)2α(cid:99)+(cid:98)3α(cid:99)+···+(cid:98)nα(cid:99)
is divisible by n.
The answer is that α must be an even integer. Let S(n,α) denote the sum in question.
¶ Analysis for α an integer. If α is an integer, then the sum equals
n(n+1)
S(n,α) = (1+2+···+n)α = ·α
2
which is obviously a multiple of n if 2 | α; meanwhile, if α is an odd integer then n = 2
gives a counterexample.
¶ Main case. Suppose α is not an integer; we show the desired condition can never be
true. Note that replacing α with α±2 changes by
S(n±2,α)−S(n,α) = 2(1+2+···+n) = n(n+1) ≡ 0 (mod n)
for every n. Thus, by shifting appropriately we may assume −1 < α < 1 and α ∈/ Z.
• If 0 < α < 1, then let m ≥ 2 be the smallest integer such that mα ≥ 1. Then
S(m,α) = 0+···+0+1 = 1
(cid:124) (cid:123)(cid:122) (cid:125)
m−1terms
is not a multiple of m.
• If −1 < α < 0, then let m ≥ 2 be the smallest integer such that mα ≤ −1. Then
S(m,α) = (−1)+···+(−1)+0 = −(m−1)
(cid:124) (cid:123)(cid:122) (cid:125)
m−1terms
is not a multiple of m.
3
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025