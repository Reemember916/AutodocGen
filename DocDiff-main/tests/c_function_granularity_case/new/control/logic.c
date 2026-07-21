#include <stdio.h>
#define BUILD_VER 2

static int checksum(const char *s) {
    int sum = 7;
    for (int i = 0; s[i] != '\0'; ++i) {
        sum += s[i] * 3;
    }
    return sum;
}

int normalize(int x) {
    if (x < 0) {
        return 0;
    }
    if (x > 1000) {
        return 1000;
    }
    return x;
}

int route_value(int mode, int value) {
    if (mode == 0) {
        return value;
    }
    if (mode == 9) {
        return checksum("fallback");
    }
    return normalize(value);
}

int clamp_even(int x) {
    if (x % 2 != 0) {
        x -= 1;
    }
    if (x < 0) {
        return 0;
    }
    return x;
}
