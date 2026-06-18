//! Rust ping benchmark: scans all hosts (1-254) in two /24 subnets
//! using threads for concurrency and system ping via std::process::Command.
//!
//! Usage: ping_rust <subnet_a_prefix> <subnet_b_prefix>
//! Example: ping_rust 192.168.1 192.168.2

use std::env;
use std::process::Command;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Instant;

const FIRST_OCTET: u8 = 1;
const LAST_OCTET: u8 = 254;
const MAX_THREADS: usize = 64;

/// Ping a single IP address using the system ping command.
/// Returns true if the host is reachable.
fn ping_host(ip: &str) -> bool {
    let output = Command::new("ping")
        .args(["-c", "1", "-W", "1", ip])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status();

    matches!(output, Ok(status) if status.success())
}

/// Scan a subnet prefix for octets 1-254 with thread-based parallelism.
/// Returns (up_count, down_count).
fn scan_subnet(prefix: &str) -> (usize, usize) {
    let up_count = Arc::new(AtomicUsize::new(0));
    let down_count = Arc::new(AtomicUsize::new(0));

    // Generate all IPs to scan
    let ips: Vec<String> = (FIRST_OCTET..=LAST_OCTET)
        .map(|octet| format!("{}.{}", prefix, octet))
        .collect();

    // Process IPs in chunks to limit concurrency
    for chunk in ips.chunks(MAX_THREADS) {
        let mut handles = Vec::with_capacity(chunk.len());

        for ip in chunk {
            let ip = ip.clone();
            let up = Arc::clone(&up_count);
            let down = Arc::clone(&down_count);

            let handle = thread::spawn(move || {
                if ping_host(&ip) {
                    up.fetch_add(1, Ordering::Relaxed);
                } else {
                    down.fetch_add(1, Ordering::Relaxed);
                }
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.join().expect("Thread panicked");
        }
    }

    (
        up_count.load(Ordering::Relaxed),
        down_count.load(Ordering::Relaxed),
    )
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let subnet_a = args.get(1).map(|s| s.as_str()).unwrap_or("192.168.1");
    let subnet_b = args.get(2).map(|s| s.as_str()).unwrap_or("192.168.2");

    println!("Rust ping benchmark");
    println!("Subnets: {}.0/24, {}.0/24", subnet_a, subnet_b);
    println!("Parallelism: {}", MAX_THREADS);
    println!("Timeout: 1s\n");

    let start = Instant::now();

    let (up_a, down_a) = scan_subnet(subnet_a);
    let (up_b, down_b) = scan_subnet(subnet_b);

    let elapsed = start.elapsed();

    println!("Subnet {}.0/24: {} up, {} down", subnet_a, up_a, down_a);
    println!("Subnet {}.0/24: {} up, {} down", subnet_b, up_b, down_b);
    println!("\nTotal time: {:.3}s", elapsed.as_secs_f64());
    println!("Hosts scanned: {}", (LAST_OCTET as usize - FIRST_OCTET as usize + 1) * 2);
}
