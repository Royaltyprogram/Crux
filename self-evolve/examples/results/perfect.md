**Answer:** 367707.

**Solution:** We will break this into multiple sections.

**Background.** First of all, the presence of the x-parameter is a technicality; informally, we are just asking for the density of primes p such that

ordp(2)>ordp(3).

The motivation of this problem comes from Artin’s primitive conjecture which asks: for which integers a are there infinitely many primes p such that a is a primitive root modulo p? This is equivalent to requesting ordp(a)=p−1, i.e. indp(a)=1.

Artin’s conjecture is open. For our purposes, the relevant fact is that the conjecture has been solved on the assumption of a generalization of the Riemann hypothesis (for zeta functions of number fields). This was done by C. Hooley in 1967.

The key idea is that a is a primitive root mod p if and only if there is no n>1 such that a is an nth power modulo p for some n∣p−1. One can try to compute the number of such primes p not exceeding x with an inclusion-exclusion argument. The Chebotarev density theorem gives us asymptotics for(1)|p≤x:p≡1(modn),a is a perfect nth power modulo p|for any fixed n.

Bounding the error terms is what we need the generalization of Riemann’s hypothesis for (c.f.: the standard RH bounds the error term in the prime number theorem); we don’t know how to do it without.

For concreteness, if a=2, then a is a primitive root modulo p for roughly 37% of primes. See [https://mathworld.wolfram.com/ArtinsConstant.html](https://mathworld.wolfram.com/ArtinsConstant.html). In general, the density is strictly positive as long as a is not a perfect square nor −1 (in which case there are no such primes p>3). The density is not quite 37% in all cases – see below for more on this.

This argument is very general: it can be adapted to look at primes p such that ordp(2)=ordp(3)=p−1, or ordp(2)=(p−1)/a,ordp(3)=(p−1)/b for fixed a,b∈Z+, or ordp(2)=ordp(3), or – you guessed it – ordp(2)>ordp(3). The “bounding the error terms” part is no more difficult in these cases, and no non-trivial complications arise. But we of course still can’t do it without GRH.

We replaced ordp(a) with ordp,x(2) for the reason of deleting the error terms, and for this reason only. As a result, when one does the inclusion-exclusion argument, there are only a finite number of terms needed, and thus we only need asymptotic formulas for (1), rather than any sharp bounds for the error term.

So the question then is about computing the main terms. To do so, one needs to be able to compute asymptotics for (1). In the case a=2, it turns out that (1) is asymptotically 1/ϕ(n)n for any square-free n. In some cases, like for a=4 and a=5, this is not the case: For a=4, take n=2. For a=5, this fails for n=10, since p≡1(mod5) implies that 5 is a square modulo p – this is related to the fact that 5∈Q(ζ5). But it turns out that there is always only a small, finite number of revisions one needs to make to the argument, allowing for the computation of the main terms.

There are a few papers considering generalizations of Artin’s conjecture. It is known that the density of primes p for which ordp(2)>ordp(3) is positive (as a special case of a more general result), this again under GRH, but the task of computing that density has not been carried out in the literature, justifying the originality of this problem. There is a fair amount of legwork and understanding needed to do this.

**Solution outline.** Here are the key steps for verifying the correctness of the answer:

1. We have _explicit_ (but cumbersome) formulas for the density d(a,b)=d(a,b,x) of primes p such that
    
    (2)ordp,x(2)=(p−1)/a,ordp,x(3)=(p−1)/b
    1. These formulas are “_quasi-multiplicative_”: they can be written in the form
        
        d(a,b)=f(v2(a),v3(a),v2(b),v3(b))∏5≤q≤xgq(vq(a),vq(b)).
        
    2. f and gq are explicit functions that can be evaluated in O(1) time.
        
2. For any fixed a, the sum
    
    ∑a<bd(a,b,x)
    
    can be evaluated in O(a) time.
    
    - Idea: We can write ∑a<bd(a,b,x)=∑b=1∞d(a,b,x)−∑b=1ad(a,b,x). The first sum is just the density of p:ordp,x(2)=(p−1)/a, which can be evaluated similarly to point 1 above. The second sum can be evaluated with brute force.
        
3. We have, for any T≥100, roughly (this omits a lower-order term)
    
    ∑T<a<bd(a,b,x)<114T−2⋅46/47,
    
    (think of the exponent as −2+ϵ), and thus we have
    
    |∑a<bd(a,b,x)−∑a<b,a≤Td(a,b,x)|<114T−2⋅46/47.
    
4. We have, for any x∞>x≥108,
    
    ∑a<b,a≤T|d(a,b,x∞)−d(a,b,x)|≤19x.
    

Then, taking T=105 and x=108, we get an answer that has error at most 2.5⋅10−8. This then gives 7 correct decimal places.

**Step 1.** In this part, we fix a,b∈Z+, and we’ll compute the density of primes p satisfying (2).

For (2) to hold, we need 2 to be a perfect ath power (and p≡1(moda)), but “no more”: 2 should not be an aqth power for any prime q (such that p≡1(modaq)). Similarly for b. It’s convenient to frame these propositions in terms of algebraic number theory.

Let K=Q(ζlcm(a,b),21/a,31/b), and for each prime q let K1,q=Q(ζaq,21/aq) and K2,q=Q(ζbq,31/bq). We want to compute the density of primes p such that p splits in K, but doesn’t split in Ki,q for any i∈1,2,2≤q≤x.

There is an “obvious guess” for what that density should be, by naively assuming that different values of q are independent (e.g. 2 being a fifth power shouldn’t provide evidence on whether 2 is a seventh power), and that there are no “spurious correlations” (e.g. 2 being a fifth power shouldn’t provide evidence on whether 3 is a fifth power or not). This intuition is almost correct: it makes a small, finite number of mistakes, namely at the primes q=2 and q=3. There are two reasons for this:

- ζ3∈Q(ζ4,3), since ζ3=(1+−3)/2.
- 2∈Q(ζ8), since we have (1+i)2=2i, and thus 1+i=ζ8⋅2.

Crucially, the _only_ relations between ζN,21/N and 31/N are these two. The following two well-known lemmas formalize this:

**Lemma 1.** Denote Kn=Q(ζn,21/n,31/n). Let N be an arbitrary positive integer (picture N as large, e.g. N=100). Let q1,q2,…,qk be pairwise distinct primes greater than three. The fields

K6N,Kq1N,…,KqkN

are linearly disjoint. This is equivalent to the Galois group of the compositum (in this case, K(6q1⋯qk)N) factorizing as the product of Galois groups of the individual fields: Gal(K(6q1⋯qk)N/Q)≅Gal(K6N/Q)×Gal(Kq1N/Q)×⋯×Gal(KqkN/Q). (Another way of saying this is that the degree of the compositum is the product of the degrees of the individual fields.) For the non-expert, this is just a way of saying “these things are independent from each other”. Furthermore, the degrees [KqiN:Q] are equal to ϕ(qiN)qi2N (“the maximum possible”).

_Proof._ We apply several results of [Järviniemi 2020](https://arxiv.org/abs/1912.02554). Recall that Q(ζq1N),…,Q(ζqKN) are linearly disjoint. We can append K6N to the set while maintaining disjointness, since the largest cyclotomic subfield of K6N lies in Q(ζ2⋅6N,2,3)⊂Q(ζ2⋅6N,ζ8,ζ12) (see Proposition 3.14 of the paper). Then, throwing in elements of the form 21/qiN and 31/qiN maintains linear disjointness, because the degrees of the resulting field extensions are powers of qi, and those are coprime. For the claim about maximality of degrees, apply Proposition 3.9 with n=qiN,K=Q(ζn),k=n2, with ai the numbers 2qix3qiy for 0≤x,y<N; the quotients of such numbers are not nth powers in K by Corollary 3.6. QED.

Of course, the claim about linear disjointness and the degrees being the maximum possible now holds for _subfields_ of K6N,Kq1N,…,KqkN, too; we’ll be using this fact throughout.

At the primes q=2,q=3 we lose a factor of 4, as promised earlier:

**Lemma 2.** For N≥3 we have [K6N:Q]=ϕ(6N)62N4.

_Proof._ Apply Proposition 3.9 with n=6N, K=Q(ζn),k=n2/4, with ai the numbers 22x3y32z3w, where 0≤x,y,z,w<N and x,z<N/2. The quotients of such numbers are not nth powers, again by Corollary 3.6. QED

With these tools, we’ll now attack the problem of computing d(a,b). Assume x is large enough that q∣ab⟹q≤x (otherwise just replace a→∏q≤xqvq(a)).

By the Chebotarev density theorem, the density of primes p splitting in a field K is [K:Q]. (Reminder for the non-expert: Splitting of primes in a number field is a somewhat technical concept, but for our purposes you only need to know that: p splitting in Q(ζn) is equivalent to p≡1(modn), and p splitting in a field like Q(ζn,21/a,31/b) (where we always assume lcm(a,b)∣n) is equivalent to p≡1(modn), 2 being an ath power and 3 being a bth power mod p. So “splitting” is exactly the thing we need.) Thus, by inclusion-exclusion,

d(a,b,x)=∑n1,n2:p∣ni⟹p≤xμ(n1)μ(n2)[Q(ζlcm(an1,bn2),21/an1,31/bn2):Q].

By the first lemma, this sum is “quasi-multiplicative” in the sense that prime powers qn with q>3 can be factored out. Explicitly, if we denote a′=2v2(a)3v3(a) and define b′ similarly, we have

d(a,b,x)=∑n1,n2∈{1,2,3,6}μ(n1)μ(n2)[Q(ζlcm(a′n1,b′n2),21/a′n1,31/b′n2):Q]×∏5≤q≤x(∑n1,n2∈{1,q}μ(n1)μ(n2)[Q(ζlcm(qvq(a)n1,qvq(b)n2),21/qvq(a)n1,31/qvq(b)n2):Q]).

The first sum over 1,2,3,62 depends only on v2(a),v2(b),v3(a),v3(b), and the sums over 1,q2 only depend on vq(a),vq(b). This proves 1(a).

For claim 1(b), we first note that for q≥5, the fields in the sum have “the maximum degree” (remember the remark about the conclusion of Lemma 1 applying to subfields, too): that is, we have

[Q(ζlcm(qvq(a)n1,qvq(b)n2),21/qvq(a)n1,31/qvq(b)n2)]=ϕ(lcm(qvq(a)n1,qvq(b)n2))qvq(a)+vq(b)n1n2.

So these sums can be computed. (Writing the formulas down explicitly isn’t necessary, since we can now write a program that computes the values.)

For the sum over n1,n2∈1,2,3,6, we need to be a bit more careful about the degrees to account for the two failures-in-maximality mentioned earlier. Denote the degree of Q(ζlcm(a′n1,b′n2),21/a′n1,31/a′n2) by D(a′n1,b′n2). By Lemma 2 (and by knowing where the factor of 4 there comes from), we can compute D(x,y). Indeed, we have

- D(x,y)=ϕ(lcm(x,y))xy/4, if we have (8∣lcm(x,y) and 2∣x) _and_ (12∣lcm(x,y) and 2∣y).
- D(x,y)=ϕ(lcm(x,y))xy/2, if we have _either_ (8∣lcm(x,y) and 2∣x) _or_ (12∣lcm(x,y) and 2∣y), but not both
- D(x,y)=ϕ(lcm(x,y))xy, if _neither_ (8∣lcm(x,y) and 2∣x) _nor_ (12∣lcm(x,y) and 2∣y) hold.

That is, we have D(x,y)=ϕ(lcm(x,y))xy⋅C(gcd(x,24),gcd(y,24)), where C:1,2,…,242→1,1/2,1/4 is explicitly given by the list above. Now, our sum can be written as

∑n1,n2∈{1,2,3,6}μ(n1)μ(n2)ϕ(lcm(a′n1,b′n2))a′n1b′n2C(gcd(a′n1,24),gcd(b′n2,24)),

which can be computed in O(1) time.

**Step 2.** Now, we fix a, and aim to evaluate the sum

∑a<bd(a,b,x)=∑b=1∞d(a,b,x)−∑b=1ad(a,b,x).

The second sum can be evaluated with brute force, and is thus not of interest to us here. Consider then the first sum. We can just forget about b altogether here: because we are summing over all of b, we are imposing no constraint on ordp,x(3); that is, we are only demanding ordp,x(2)=(p−1)/a. (Technical point: we’re assuming here that limN→∞∑a,b≤Nd(a,b,x)=1; see Step 3 for more on this.)

Now, the density d(a,x) of p such that ordp,x(2)=(p−1)/a can be computed similarly to the computations in Part 1. But it’s much simpler: note that [Q(ζn,21/n):Q] is always at least nϕ(n)/2 – we lose only a factor of 2, not a factor of 4 like in Lemma 2, since we only have the failure at 8∣n coming from 2∈Q(ζ8). And so our formula is multiplicative:

d(a,x)=∏2≤q≤x∑n∈{1,q}μ(n)[Q(ζqvq(a)n,q1/qvq(a)n):Q].

Furthermore, the terms are easy to calculate: If q>2, then they are

1ϕ(qvq(a))qvq(a)(1−1q2).

For q=2, the values are (for vq(a)=0,1,2,…)

12,38,116,364,3256,31024,…

**Step 3.** We now want to bound tail sums of d(a,b,x); the basic idea is to give pointwise bounds for d(a,b,x) and then sum those bounds.

**Lemma 3.** For any a,b and x we have

d(a,b,x)≤4ϕ(lcm(a,b))ab.

The proof is simple: the condition ordp,x(2)=(p−1)/a,ordp,x(3)=(p−1)/b in particular implies that p splits in Q(ζlcm(a,b),21/a,31/b), which has at least degree ϕ(lcm(a,b))ab/4 – see the previous two lemmas.

Here is a very basic tail sum bound.

**Lemma 4.** We have limT→∞∑a,b≤Td(a,b,x)=1.

For the proof, note that

∑a,b:max(a,b)>Td(a,b,x)≤∑a,b:max(a,b)>T4ϕ(lcm(a,b))ab≪∑a>T1aϕ(a)∑1≤b≤T1b.

The inner sum is O(log⁡T). For the outer sum, we have well-known bound ϕ(a)≫a, and so ∑a>T1/(aϕ(a))≪1/T, so the whole sum is O(log⁡T/T)=o(1).

Further note that d(1,2,x) is strictly positive (roughly 12.5%). Together with the previous lemma this implies that the density of p with ordp,x(2)>ordp,x(3) equals

∑(a,b)∈Z+2:a<bd(a,b,x).

(An intuitive but non-trivial, technical claim – we in fact haven’t proven such results if x is replaced with ∞, and this is the reason Artin’s primitive conjecture is still open.)

Now, we want quantitative, strong bounds for

∑T<a<bd(a,b,x).

For this, we’ll use the fact that

ϕ(n)≥c1(nc2)δ,

where c1=92160,c2=510510,δ=46/47. (See [https://math.stackexchange.com/questions/301837/is-the-euler-phi-function-bounded-below](https://math.stackexchange.com/questions/301837/is-the-euler-phi-function-bounded-below).) We have

∑T<a<bd(a,b,x)≤4∑T<a<b1ϕ(lcm(a,b))ab<2c2δc1∑T<a,b1ablcm(a,b)1+δ.

Continue:

2c2δc1∑T<a,b1ablcm(a,b)δ=2c2δc1∑T<a,bgcd(a,b)δ(ab)1+δ≤2c2δc1∑d=1∞dδ∑T/d<a′,b′1(da′db′)1+δ=2c2δc1∑d=1∞d−2−δ(∑T/d<n1n1+δ)2.

The inner sum is bounded by ∫T/d∞1/t1+δdt=δ−1(T/d)−δ (plus 1 for d>T). And thus, the above is bounded as

2c2δc1δ2∑d=1∞d−2−δ((dT)2δ+1d>T).

The sum over d without the 1d>T part can be bounded numerically for δ=46/47 as 13, and the 1d>T part introduces an additional (small) contribution of T−1−δ/(1+δ), and so we arrive at

2c2δc1δ2(13T−2δ+T−1−δ/(1+δ)).

For T=105 this is less than 2⋅10−8.

**Step 4.** We want to bound the difference that arises from replacing a particular value of x in d(a,b,x) with an arbitrarily large value of x=x∞. Recall the function gq(vq(a),vq(b)) from Part 1. We have gq(0,0)=1−2/q(q−1)+1/q2(q−1). In particular,

∏q>x is primegq(0,0)≥∏q>x is prime(1−2(q−1)2).

Now, when 0≤t≤1/100, we have 1−t⋅0.99≥e−t, so the above is bounded from below by

∏q>x is primee−1.98/(q−1)2≥exp⁡(∑q>x is prime−1.98/(q−1)2).

For y≥108, there are at most 1.1y/log⁡(y) primes in the interval [y,2y), and thus by dyadic decomposition

∑q>x is prime1.98(q−1)2≤∑y=2kx,k≥01.98y21.1ylog⁡(y)=1.98⋅1.1x∑k≥012k(klog⁡(2)+log⁡(x)),

which for x≥108 is numerically bounded by 1/9x. Thus, we arrive at the lower bound exp⁡(−1/9x)≥1−19x.

Thus, for any x∞>x>max(a,b) (the last condition needed so that vq(a)=vq(b)=0 for q≥x) with x≥108, we have

0≥d(a,b,x∞)−d(a,b,x)≥d(a,b,x)(1−19x)−d(a,b,x)≥19xd(a,b,x).

And, since ∑a<b,a≤Td(a,b,x)≤1, we have

∑a<b,a≤T|d(a,b,x∞)−d(a,b,x)|≤19x.