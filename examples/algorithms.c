/* Small classic algorithms, used as end-to-end tests: C -> clang -> AArch64 -> CPU and QPU. */

int gcd(int a, int b) { while (b) { int t = a % b; a = b; b = t; } return a; }

int fib(int n) { int a = 0, b = 1; for (int i = 0; i < n; i++) { int t = a + b; a = b; b = t; } return a; }

int is_prime(int n) {
    if (n < 2) return 0;
    for (int d = 2; d * d <= n; d++)
        if (n % d == 0) return 0;
    return 1;
}

int popcount(unsigned x) { int c = 0; while (x) { c += x & 1; x >>= 1; } return c; }

int collatz_steps(int n) { int s = 0; while (n != 1) { n = (n & 1) ? 3 * n + 1 : n / 2; s++; } return s; }

int isqrt(int n) { int r = 0; while ((r + 1) * (r + 1) <= n) r++; return r; }

int power_mod(int b, int e, int m) {
    int r = 1; b %= m;
    while (e > 0) { if (e & 1) r = (r * b) % m; b = (b * b) % m; e >>= 1; }
    return r;
}

int max3(int a, int b, int c) { int m = a > b ? a : b; return m > c ? m : c; }

static int sq(int x) { return x * x; }
int sum_of_squares(int a, int b) { return sq(a) + sq(b); }

void bubble_sort(int *a, int n) {
    for (int i = 0; i < n; i++)
        for (int j = 0; j + 1 < n - i; j++)
            if (a[j] > a[j + 1]) { int t = a[j]; a[j] = a[j + 1]; a[j + 1] = t; }
}

int binary_search(const int *a, int n, int key) {
    int lo = 0, hi = n - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (a[mid] == key) return mid;
        if (a[mid] < key) lo = mid + 1; else hi = mid - 1;
    }
    return -1;
}

int digit_sum(int n) { int s = 0; while (n > 0) { s += n % 10; n /= 10; } return s; }
