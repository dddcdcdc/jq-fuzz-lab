/* Write each newly executed guard ID once. Compile this file without instrumentation. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

void __sanitizer_cov_trace_pc_guard_init(uint32_t *start, uint32_t *stop) {
    static uint32_t next_id;
    if (start == stop || *start != 0)
        return;
    for (uint32_t *guard = start; guard < stop; ++guard)
        *guard = ++next_id;
}

void __sanitizer_cov_trace_pc_guard(uint32_t *guard) {
    static int fd = -2;
    if (*guard == 0)
        return;
    if (fd == -2) {
        const char *path = getenv("FUZZ_COVERAGE_FILE");
        fd = path ? open(path, O_WRONLY | O_CREAT | O_TRUNC, 0600) : -1;
    }
    if (fd >= 0) {
        char record[24];
        int size = snprintf(record, sizeof(record), "%u\n", (unsigned)*guard);
        if (size > 0 && (size_t)size < sizeof(record))
            (void)write(fd, record, (size_t)size);
    }
    *guard = 0;
}
