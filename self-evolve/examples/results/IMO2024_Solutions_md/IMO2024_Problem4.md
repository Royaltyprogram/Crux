# IMO 2024 Problem 4 Solution

§2.1 IMO 2024/4, proposed by Dominik Burek (POL)
Available online at https://aops.com/community/p31218657.
Problem statement
Let triangle ABC with incenter I satisfying AB < AC < BC. Let X be a point
on line BC, different from C, such that the line through X and parallel to AC is
tangent to the incircle. Similarly, let Y be a point on line BC, different from B,
such that the line through Y and parallel to AB is tangent to the incircle. Line
AI intersects the circumcircle of triangle ABC again at P. Let K and L be the
midpoints of AC and AB, respectively. Prove that ∠KIL+∠YPX = 180◦.
Let T be the reflection of A over I, the most important point to add since it gets rid of
K and L as follows.
Claim — We have ∠KIL = ∠BTC, and lines TX and TY are tangent to the
incircle.
Proof. The first part is true since (cid:52)BTC is the image of (cid:52)KIL under a homothety of
ratio 2. The second part is true because lines AB, AC, TX, TY determine a rhombus
with center I.
We thus delete K and L from the picture altogether; they aren’t needed anymore.
A
K L
I
B C
X Y
T
P
10
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025
Claim — We have BXPT and CYPT are cyclic.
Proof. (cid:93)TYC = (cid:93)TYB = (cid:93)ABC = (cid:93)APC = (cid:93)TPC and similarly. (Some people call
this Reim’s theorem.)
To finish, observe that
(cid:93)CTB = (cid:93)CTP +(cid:93)PTB = (cid:93)CYP +(cid:93)PXB = (cid:93)XYP +(cid:93)XYP = (cid:93)XPY
as desired. (The length conditions AC > AB > BC ensure that B, X, Y, C are collinear
in that order, and that T lies on the opposite side of BC as A. Hence the directed
equality (cid:93)CTB = (cid:93)XPY translates to the undirected ∠BTC +∠XPY = 180◦.)
11
IMO 2024 Solution Notes web.evanchen.cc, updated 30 May 2025