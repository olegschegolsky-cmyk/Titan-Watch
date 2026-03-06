# Titan-Watch
A high-performance, asynchronous terminal system monitor featuring reactive stream processing, Braille sparklines, and a metaclass-based plugin architecture—all in a single Python file

# Titan-Watch

A distributed, asynchronous system resource monitor built for the terminal. 

Titan-Watch demonstrates advanced Python architectural concepts—such as the Reactor pattern, metaclass registries, and ring buffers—condensed into a single, dependency-light file. It provides real-time monitoring of CPU, RAM, Network, and Disk usage with double-buffered ANSI rendering and Braille-based sparklines.

## Features

* **Reactive Stream Processing:** Uses `asyncio` to manage data ingestion and UI rendering in separate non-blocking tasks.
* **Metaclass Plugin Architecture:** Collectors (CPU, Memory, Network, Disk) are automatically registered via the `CollectorRegistry` metaclass. Adding a new metric is as simple as subclassing `BaseCollector`.
* **Optimized Memory Management:** Employs `__slots__` and a custom `RingBuffer` to calculate moving averages (O(1) time complexity) without unbounded memory growth.
* **Advanced Terminal UI:** Features double-buffering to prevent screen flickering, ANSI escape sequences for color/cursor control, and dynamic Braille sparklines.
* **Graceful Shutdown:** Handles `SIGINT` and `SIGTERM` cleanly, ensuring the terminal cursor and states are restored upon exit.

## Requirements

* **Python:** 3.10 or higher (uses modern type hinting and `asyncio` features).
* **Dependencies:** `psutil` (The only external dependency, used for fetching system metrics).

## Installation & Usage

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/yourusername/titan-watch.git](https://github.com/yourusername/titan-watch.git)
    cd titan-watch
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install the required dependency:**
    ```bash
    pip install psutil
    ```

4.  **Run the monitor:**
    ```bash
    python titan_watch.py
    ```

## Architecture Overview

Titan-Watch is divided into four main logical layers within a single file:

1.  **Data Layer (`RingBuffer`, `MetricValue`):** Handles the storage and mathematical aggregation of metrics. The custom ring buffer keeps a running sum to compute the 60-second moving average instantly.
2.  **Collector Layer (`BaseCollector`, `CPUCollector`, etc.):** Interfaces with the OS via `psutil`. The `CollectorRegistry` metaclass automatically detects and registers any new collector classes.
3.  **Rendering Engine (`TerminalRenderer`):** Manages raw ANSI terminal codes. It builds the entire visual frame in memory (double-buffering) before flushing it to `sys.stdout`.
4.  **Orchestrator (`TaskScheduler`):** The heart of the application. It spins up the `asyncio` event loop, managing the periodic tick rate (FPS) for both data collection and UI updates.

## Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/yourusername/titan-watch/issues).

## License
This project is [MIT](https://opensource.org/licenses/MIT) licensed.
