/* Trial-division factorization. Compile for AArch64, then run the same binary on the QPU. */

/* smallest prime factor of n (n itself if n is prime) */
int smallest_factor(int n) {
    for (int d = 2; d * d <= n; d++)
        if (n % d == 0)
            return d;
    return n;
}

/* writes the prime factors of n into out[], returns how many there are */
int factorize(int n, int *out) {
    int k = 0;
    while (n > 1) {
        int p = smallest_factor(n);
        out[k++] = p;
        n /= p;
    }
    return k;
}
