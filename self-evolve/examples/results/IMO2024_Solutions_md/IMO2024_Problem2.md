# IMO 2024 Problem 2 Solution

§1.2 IMO 2024/2, proposed by Valentino Iverson (IDN)
Available online at https://aops.com/community/p31205957.
Problem statement
For which pairs of positive integers (a,b) is the sequence
gcd(an+b,bn+a) n = 1,2,...
eventually constant?
The answer is (a,b) = (1,1) only, which obviously works since the sequence is always 2.
Conversely, assume the sequence
xn := gcd(an+b,bn+a)
is eventually constant. The main crux of the other direction is to consider
M := ab+1.
Remark (Motivation). The reason to consider the number is the same technique used in
IMO 2005/4, namely the idea to consider “n = −1”. The point is that the two rational
numbers
1 ab+1 1 ab+1
+b= , +a=
a b b a
have a large common factor: we could write “x−1 =ab+1”, loosely speaking.
Now, the sequence is really only defined for n ≥ 1, so one should instead take n ≡ −1
(mod ϕ(M)) — and this is exactly what we do.
Obviously gcd(a,M) = gcd(b,M) = 1. Let n be a sufficiently large multiple of ϕ(M) so
that
x = x = x = ··· .
n−1 n n+1
We consider the first three terms; the first one is the “key” one that gets the bulk of the
work, and the rest is bookkeeping and extraction.
• Consider xn−1. Note that
a(an−1+b) = an+ab ≡ 1+(−1) ≡ 0 (mod M)
and similarly b(bn+a) ≡ 0 (mod M). Hence M | xn−1.
• Consider xn, which is now known to be divisible by M. Note that
0 ≡ an+b ≡ 1+b (mod M)
0 ≡ bn+a ≡ 1+a (mod M).
So a ≡ b ≡ −1 (mod M).
• Consider xn+1, which is now known to be divisible by M. Note that
0 ≡ an+1+b ≡ bn+1+a ≡ a+b (mod M).
We knew a ≡ b ≡ −1 (mod M), hence this means 0 ≡ 2 (mod M), so M = 2.
From M = 2 we then conclude a = b = 1, as desired.
4
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025
Remark (No alternate solutions known). At the time nobody seems to know any solution
not depending critically on M =ab+1 (or prime numbers dividing M, etc.). They vary in
executiononcesometermoftheformx istaken,butavoidingthekeyideaaltogether
kϕ(n)−1
does not currently seem possible.
A good example to consider for ruling out candidate ideas is (a,b)=(18,9).
5
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025