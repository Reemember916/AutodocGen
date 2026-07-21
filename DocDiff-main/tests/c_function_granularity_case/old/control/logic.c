#include <stdio.h>
#define BUILD_VER 1

static int checksum(const char *s) {
    int sum = 0;
    for (int i = 0; s[i] != '\0'; ++i) {
        sum += s[i];
    }
    return sum;
}

int normalize(int x) {
    if (x < 0) {
        return 0;
    }
    if (x > 100) {
        return 100;
    }
    return x;
}

int route_value(int mode, int value) {
    if (mode == 0) {
        return value;
    }
    return normalize(value);
}
