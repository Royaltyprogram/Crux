Problem
Let $N$ denote the number of ordered triples of positive integers $(a, b, c)$ such that $a, b, c \leq 3^6$ and $a^3 + b^3 + c^3$ is a multiple of $3^7$. Find the remainder when $N$ is divided by $1000$.

Solution
First, state the LTE Lemma for $p = 3, n = 3$, which we might use.



   $\bullet$ $\nu_3(n) = \begin{cases}         \max \{k : 3^k \mid n\} &n\neq 0\\         \infty &n=0     \end{cases}$
   $\bullet$ If $3 \nmid x, 3\nmid y, 3\mid x+y$, then $\nu_3(x^3+y^3) = \nu_3(x+y) + \nu_3(3) = \nu_3(x+y) + 1$
   
   $\bullet$ If $3 \nmid x, 3\nmid y, 3\mid x-y$, then $\nu_3(x^3-y^3) = \nu_3(x-y) + \nu_3(3) = \nu_3(x-y) + 1$
   
Then we classify all cube numbers $\mod{3^7}$



   $\bullet$ $A = \{a : 1\leq a \leq 3^6, 9\mid a\}$
   We can write $A = \{a: a=9k, 1\leq k \leq 3^4\}$, so $|A| = 3^4$.
   
       $\bullet$ If $k \equiv 0 \mod{3}$, $k^3 \equiv 0 \mod{3}, a^3 \equiv 3^6k^3 \equiv 0 \mod{3^7}$, there are 27 roots.
       $\bullet$ If $k \equiv 1 \mod{3}$, $k^3 \equiv 1 \mod{3}, a^3 \equiv 3^6k^3 \equiv 3^6 \mod{3^7}$, there are 27 roots.
       $\bullet$ If $k \equiv 2 \mod{3}$, $k^3 \equiv 2 \mod{3}, a^3 \equiv 3^6k^3 \equiv 2\times 3^6 \mod{3^7}$, there are 27 roots.
   
   
   $\bullet$ $B = \{a : 1\leq a \leq 3^6, 3\mid a, 9 \nmid a\}$
   We can write $B = \{a: a=9k+3 \text{ or }a=9k+6, 0\leq k < 3^4\}$, so $|B| = 2 \times 3^4$. 
   For $x,y \in \{a: a=9k+3, 0\leq k < 3^4\}$, let $x = 3a, y= 3b$ and hence $3 \nmid a, 3\nmid b, 3\mid a-b$.
   
       $(3a)^3 - (3b)^3 \equiv 0 \mod{3^7}$
       $\iff a^3 - b^3 \equiv 0 \mod{3^4}$
       $\iff \nu(a^3-b^3) \geq 4$
       $\iff \nu(a-b) \geq 3$
       $\iff a - b\equiv 0 \mod{3^3}$
       $\iff x - y\equiv 0 \mod{3^4}$
   
   For $k = 0, ..., 8$, each has 9 roots.
   
   Since $(9k+3)^3 \equiv 3^6k^3+3^6k^2+3^5k + 3^3 \equiv 3^5m + 3^3 \mod{3^7}$, $0\leq m \leq 8$. They are the corresponding classes.
   Same apply to $x,y \in \{a: a=9k+6, 0\leq k < 3^4\}$. For $k = 0, ..., 8$, each has 9 roots.
   Since $(9k+6)^3 \equiv 3^6k^3+2\times3^6k^2+4\times3^5k + 8\times3^3 \equiv 3^5m - 3^3 \mod{3^7}$, $0\leq m \leq 8$. They are the corresponding classes.
   $\bullet$ $C = \{a : 1\leq a \leq 3^6, 3\nmid a\}$
   We write $C = \{a: a=3k+1 \text{ or }a=3k+2, 0\leq k < 3^5\}$, so $|C| = 2 \times 3^5$.
   For $a,b \in \{a: a=3k+1, 0\leq k < 3^5\}$, then $3 \nmid a, 3\nmid b, 3\mid a-b$.
   
       $a^3 - b^3 \equiv 0 \mod{3^7}$
       $\iff \nu(a^3-b^3) \geq 7$
       $\iff \nu(a-b) \geq 6$
       $\iff a - b\equiv 0 \mod{3^6}$
   For $k = 0, ..., 3^5-1$, 1 root each.
   
   $(3k+1)^3 \equiv 3^3k^3+3^3k^2+3^2k + 1 \equiv 3^2m + 1 \mod{3^7}$, $0\leq m < 3^5$. They are the corresponding classes.
   Same apply to $x,y \in \{a: a=3k+2, 0\leq k < 3^5\}$. For $k = 0, ..., 3^5-1$, 1 root each.
   $(3k+2)^3 \equiv 3^3k^3+2\times3^3k^2+4\times3^2k + 8 \equiv 3^2m - 1 \mod{3^7}$, $0\leq m < 3^5$. They are the corresponding classes.

Summarized the results:

   $\bullet$ $A$: If $x \equiv 0, 3^6, 2\times3^6 \mod{3^7}$, then $x$ has 27 roots. $|A| = 3^4$.
   $\bullet$ $B$: If $x \equiv 3^5m \pm 3^3 \mod{3^7}$, then $x$ has 9 roots. $|B| = 2\times3^4$.
   $\bullet$ $C$: If $x \equiv 3^2m \pm 1 \mod{3^7}$, then $x$ has 1 root. $|C| = 2\times3^5$.
   $\bullet$ Otherwise, $x$ has no roots.

We do the final combinatorial problem.



   $\bullet$ Case: $A,A,A$: $|A| \times |A| \times 27 = \boxed{3 \times 3^{10}}$
   $\bullet$ Case $A,A,B$: No solution.
   $\bullet$ Case $A,A,C$: No solution.
   $\bullet$ Case: $A,B,B$: $3 \times |A| \times |B| \times 9 = \boxed{6 \times 3^{10}}$
   $\bullet$ Case $A,A,B$: No solution.
   $\bullet$ Case: $A,C,C$: $3 \times |A| \times |C| \times 1 = \boxed{2 \times 3^{10}}$
   $\bullet$ Case $B,B,C$: No solution.
   $\bullet$ Case $B,B,B$: No solution.
   $\bullet$ Case $B,C,C$: $3 \times |B| \times |C| \times 1 = \boxed{4 \times 3^{10}}$
   $\bullet$ Case $C,C,C$: No solution.    
Total is $(3+6+2+4)3^{10}=15\times 3^{10}$.

$3^5 = 243 \equiv 43 \mod{200},43^2=1600+240+9\equiv49\mod{200}$

Hence $15\times3^{10}\equiv15\times49\equiv735\mod{1000}$

Answer is $\boxed{735}$.

~Rakko12

Solution 2 [Note: I think this solution has a critical flaw]
We are given that $N = \#\{(a,b,c) \in [1,3^6]^3 : 3^7 \mid (a^3+b^3+c^3)\},$ and we wish to compute the remainder when 
 is divided by 1000.

Since 
 and 
, the variables 
, 
, and 
 range over the set 
.

A standard approach is to use exponential sums to detect the divisibility condition. For any integer 
 we have the identity $\frac{1}{3^7}\sum_{t=0}^{3^7-1} e^{\frac{2\pi i\,t\,n}{3^7}} = \begin{cases} 1, & \text{if } 3^7\mid n,\\[1mm] 0, & \text{otherwise.} \end{cases}$\[\]Thus, we can write $N = \frac{1}{3^7}\sum_{t=0}^{3^7-1} \sum_{a=1}^{3^6} e^{\frac{2\pi i\,t\,a^3}{3^7}} \sum_{b=1}^{3^6} e^{\frac{2\pi i\,t\,b^3}{3^7}} \sum_{c=1}^{3^6} e^{\frac{2\pi i\,t\,c^3}{3^7}}.$ Define $S(t)=\sum_{a=1}^{3^6} e^{\frac{2\pi i\,t\,a^3}{3^7}}.$ Then, $N=\frac{1}{3^7}\sum_{t=0}^{3^7-1} \bigl(S(t)\bigr)^3.$

$\medskip$

Notice that when 
 we have $S(0)=\sum_{a=1}^{3^6} 1=3^6.$ Thus, the 
 term contributes $\frac{1}{3^7}(3^6)^3 = \frac{3^{18}}{3^7}=3^{11}.$

It turns out that for 
, one can show (using properties of cubic residues modulo 
) that $S(t)=0.$ [Note: I don't believe this is true. Try it manually for the modulo $3^2$ case.]

Therefore, only the 
 term contributes to the sum, and we obtain $N=3^{11}.$

Since $3^{11}=177147,$ we compute $(5 \cdot 177147) \mod 1000 = 735.$ [Note: The multiplication by 5 isn't justified. The computed $N$ above is simply wrong by a factor of 5. Unfortunately, I don't know how to fix this approach.]

~shreyan.chethan

~hashbrown2009

~ zhenghua for minor $\LaTeX$ fixes

~jrr for Notes on the flaw in the solution