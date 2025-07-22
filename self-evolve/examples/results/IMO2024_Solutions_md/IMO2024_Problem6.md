# IMO 2024 Problem 6 Solution

§2.3 IMO 2024/6, proposed by Japan
Available online at https://aops.com/community/p31218720.
Problem statement
A function f: Q → Q is called aquaesulian if the following property holds: for every
x,y ∈ Q,
f(x+f(y)) = f(x)+y or f(f(x)+y) = x+f(y).
Show that there exists an integer c such that for any aquaesulian function f there
are at most c different rational numbers of the form f(r)+f(−r) for some rational
number r, and find the smallest possible value of c.
We will prove that
{f(x)+f(−x) | x ∈ Q}
contains at most 2 elements and give an example where there are indeed 2 elements.
We fix the notation x → y to mean that f(x+f(y)) = f(x)+y. So the problem
statement means that either x → y or y → x for all x, y. In particular, we always have
x → x, and hence
f(x+f(x)) = x+f(x)
for every x.
¶ Construction. The function
f(x) = (cid:98)2x(cid:99)−x
can be seen to satisfy the problem conditions. Moreover, f(0)+f(0) = 0 but f(1/3)+
f(−1/3) = −1.
Remark. Here is how I (Evan) found the construction. Let h(x) := x+f(x), and let
S :=h(Q)={h(x)|x∈Q}. Hence f is the identity on all of S. If we rewrite the problem
condition in terms of h instead of f, it asserts that at least one of the equations
h(x+h(y)−y)=h(x)+h(y)
h(y+h(x)−x)=h(x)+h(y)
is true. In particular, S is closed under addition.
Now, the two trivial solutions for h are h(x) = 2x and h(x) = 0. To get a nontrivial
construction, we must also have S (cid:54)={0} and S (cid:54)=Q. So a natural guess is to take S =Z.
And indeed h(x)=(cid:98)2x(cid:99) works fine.
Remark. This construction is far from unique. For example, f(x)=2(cid:98)x(cid:99)−x=(cid:98)x(cid:99)−{x}
seems to have been more popular to find.
¶ Proof (communicated by Abel George Mathew). We start by proving:
Claim — f is injective.
17
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025
Proof. Suppose f(a) = f(b). WLOG a → b. Then
f(a)+a = f(a+f(a)) = f(a+f(b)) = f(a)+b =⇒ a = b. .
Claim — Suppose s → r. Then either f(r)+f(−r) = 0 or f(f(s)) = s+f(r)+
f(−r).
Proof. Take the given statement with x = s+f(r) and y = −r; then
x+f(y) = s+f(r)+f(−r)
y+f(x) = f(s+f(r))−r = f(s).
Because f is injective, if x → y then f(r)+f(−r) = 0. Meanwhile, if y → x then indeed
f(f(s)) = s+f(r)+f(−r).
Finally, suppose a and b are different numbers for which f(a)+f(−a) and f(b)+f(−b)
are both nonzero. Again, WLOG a → b. Then
a→a a→b
f(a)+f(−a) = f(f(a))−a = f(b)+f(−b).
This shows at most two values can occur.
Remark. The above solution works equally well for f: R→R. But the choice of Q permits
some additional alternate solutions.
Remark. After showing f injective, a common lemma proved is that −f(−f(x))=x, i.e.
f is an involution. This provides some alternative paths for solutions.
18