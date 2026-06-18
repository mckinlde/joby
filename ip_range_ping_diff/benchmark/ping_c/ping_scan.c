/**
 * C ping benchmark: scans all hosts (1-254) in two /24 subnets
 * using fork/exec to call the system ping command with parallelism.
 *
 * Usage: ./ping_scan <subnet_a_prefix> <subnet_b_prefix>
 * Example: ./ping_scan 192.168.1 192.168.2
 *
 * Outputs timing and reachability results to stdout.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <unistd.h>

#define FIRST_OCTET 1
#define LAST_OCTET 254
#define MAX_PARALLEL 64
#define TIMEOUT_SEC "1"
#define IP_BUF_SIZE 20

/**
 * Ping a single IP address using fork/exec.
 * Returns 0 if host is reachable, non-zero otherwise.
 */
static int ping_host(const char *ip) {
    pid_t pid = fork();
    if (pid < 0) {
        perror("fork");
        return -1;
    }

    if (pid == 0) {
        /* Child process: exec ping with timeout */
        /* Redirect stdout/stderr to /dev/null */
        freopen("/dev/null", "w", stdout);
        freopen("/dev/null", "w", stderr);
        execlp("ping", "ping", "-c", "1", "-W", TIMEOUT_SEC, ip, (char *)NULL);
        /* If exec fails */
        _exit(127);
    }

    /* Parent: wait for child */
    int status;
    waitpid(pid, &status, 0);

    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    return -1;
}

/**
 * Get current time in seconds (monotonic-ish via gettimeofday).
 */
static double get_time_sec(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec + tv.tv_usec / 1000000.0;
}

/**
 * Scan a subnet prefix for octets 1-254 with limited parallelism.
 * Uses fork to run multiple pings concurrently.
 */
static void scan_subnet(const char *prefix, int *up_count, int *down_count) {
    int active = 0;
    int octet = FIRST_OCTET;
    *up_count = 0;
    *down_count = 0;

    /* Track child PIDs and their octets */
    pid_t pids[MAX_PARALLEL];
    int octets[MAX_PARALLEL];
    memset(pids, 0, sizeof(pids));

    while (octet <= LAST_OCTET || active > 0) {
        /* Launch new children up to MAX_PARALLEL */
        while (active < MAX_PARALLEL && octet <= LAST_OCTET) {
            char ip[IP_BUF_SIZE];
            snprintf(ip, sizeof(ip), "%s.%d", prefix, octet);

            pid_t pid = fork();
            if (pid < 0) {
                perror("fork");
                octet++;
                continue;
            }

            if (pid == 0) {
                /* Child: exec ping */
                freopen("/dev/null", "w", stdout);
                freopen("/dev/null", "w", stderr);
                execlp("ping", "ping", "-c", "1", "-W", TIMEOUT_SEC, ip,
                       (char *)NULL);
                _exit(127);
            }

            /* Find a free slot */
            for (int i = 0; i < MAX_PARALLEL; i++) {
                if (pids[i] == 0) {
                    pids[i] = pid;
                    octets[i] = octet;
                    break;
                }
            }
            active++;
            octet++;
        }

        /* Wait for any child to finish */
        if (active > 0) {
            int status;
            pid_t done = wait(&status);
            if (done > 0) {
                active--;
                /* Find which slot this PID was in and clear it */
                for (int i = 0; i < MAX_PARALLEL; i++) {
                    if (pids[i] == done) {
                        if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
                            (*up_count)++;
                        } else {
                            (*down_count)++;
                        }
                        pids[i] = 0;
                        break;
                    }
                }
            }
        }
    }
}

int main(int argc, char *argv[]) {
    const char *subnet_a = (argc > 1) ? argv[1] : "192.168.1";
    const char *subnet_b = (argc > 2) ? argv[2] : "192.168.2";

    printf("C ping benchmark\n");
    printf("Subnets: %s.0/24, %s.0/24\n", subnet_a, subnet_b);
    printf("Parallelism: %d\n", MAX_PARALLEL);
    printf("Timeout: %ss\n\n", TIMEOUT_SEC);

    double start = get_time_sec();

    int up_a = 0, down_a = 0;
    int up_b = 0, down_b = 0;

    scan_subnet(subnet_a, &up_a, &down_a);
    scan_subnet(subnet_b, &up_b, &down_b);

    double elapsed = get_time_sec() - start;

    printf("Subnet %s.0/24: %d up, %d down\n", subnet_a, up_a, down_a);
    printf("Subnet %s.0/24: %d up, %d down\n", subnet_b, up_b, down_b);
    printf("\nTotal time: %.3fs\n", elapsed);
    printf("Hosts scanned: %d\n", (LAST_OCTET - FIRST_OCTET + 1) * 2);

    return 0;
}
