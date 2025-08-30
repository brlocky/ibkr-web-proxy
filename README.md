# IBKR Proxy Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A lightweight Python FastAPI proxy server that bridges web applications to Interactive Brokers Gateway/TWS via REST API.

## Why This Proxy?

Web browsers cannot directly connect to IB Gateway's TCP socket (port 7497/7496) due to CORS and security restrictions. This proxy:

- **Solves CORS Issues**: Enables web apps to access IB data without browser security blocks
- **Simplifies Integration**: Provides clean REST API instead of complex socket programming
- **Handles Connections**: Manages IB Gateway connection lifecycle and reconnection
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Architecture

```
Web App (React/Vue/etc) → HTTP REST API → Python Proxy → IB Gateway/TWS (TCP 7497)
                         (localhost:3005)              (localhost:7497)
```

## Quick Start

### Prerequisites
- Python 3.8 or higher
- Interactive Brokers Gateway or TWS with API enabled

### Installation

1. **Clone and install dependencies:**
```bash
git clone <repository-url>
cd ibkr-proxy
pip install -r requirements.txt
```

2. **Start IB Gateway/TWS:**
   - Enable API connections in settings
   - Default ports: Gateway (7497), TWS (7496)

3. **Run the proxy:**
```bash
python main.py
```

Proxy will be available at `http://localhost:3005`

## Configuration

### Command Line Options

```bash
python main.py --help

# Custom ports
python main.py --ib-port 7496 --proxy-port 8080

# Different host
python main.py --ib-host 192.168.1.100 --proxy-host 0.0.0.0

# Custom client ID
python main.py --client-id 2
```

### Available Options

| Option | Default | Description |
|--------|---------|-------------|
| `--ib-host` | 127.0.0.1 | IB Gateway/TWS host |
| `--ib-port` | 7497 | IB Gateway/TWS port (7497=Gateway, 7496=TWS) |
| `--proxy-host` | 127.0.0.1 | Proxy server host |
| `--proxy-port` | 3005 | Proxy server port |
| `--client-id` | 1 | IB API client ID |

## Cross-Platform Setup

### Windows

**Option 1: Use Pre-built Executable** ✅
- Download `ibkr-proxy-windows.exe` from releases
- Double-click to run or use command line:
```cmd
ibkr-proxy-windows.exe --ib-port 7497 --proxy-port 3005
```

**Option 2: Python Installation**
```cmd
# Install Python from python.org
pip install -r requirements.txt
python main.py
```

### macOS

**Option 1: Use Pre-built Binary** (Available via GitHub Actions)
```bash
# Download ibkr-proxy-macos from releases
chmod +x ibkr-proxy-macos
./ibkr-proxy-macos --ib-port 7497 --proxy-port 3005
```

**Option 2: Python Installation** ✅ Recommended
```bash
# Install Python via Homebrew
brew install python
pip3 install -r requirements.txt
python3 main.py
```

### Linux

**Option 1: Use Pre-built Binary** (Available via GitHub Actions)
```bash
# Download ibkr-proxy-linux from releases
chmod +x ibkr-proxy-linux
./ibkr-proxy-linux --ib-port 7497 --proxy-port 3005
```

**Option 2: Python Installation** ✅ Recommended
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip
pip3 install -r requirements.txt
python3 main.py

# CentOS/RHEL
sudo yum install python3 python3-pip
pip3 install -r requirements.txt
python3 main.py
```

## Building Executables

### Build for Current Platform
```bash
python build.py
```
Executable will be in `dist/` folder.

### Cross-Platform Building

**Important:** PyInstaller creates platform-specific executables. You need to build on each target OS.

**Manual Building:**
- Windows: Run `python build.py` on Windows → `ibkr-proxy-windows.exe`
- macOS: Run `python build.py` on macOS → `ibkr-proxy-macos`  
- Linux: Run `python build.py` on Linux → `ibkr-proxy-linux`

**Automated Building (GitHub Actions):**
The repository includes a GitHub Actions workflow that automatically builds for all platforms when you create a release tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

This will create executables for Windows, macOS, and Linux automatically.

## API Reference

### Connection & Health
- `GET /health` - Check proxy and IB connection status

### Account & Portfolio
- `GET /accounts` - Get managed accounts
- `GET /positions/{account_id}` - Get account positions

### Market Data
- `GET /search?symbol=AAPL` - Search contracts by symbol
- `GET /loadData?conId=123&interval=1min&limit=100` - Load historical data
- `GET /loadMoreData?conId=123&interval=1min&endTime=1234567890` - Load more historical data
- `GET /getSymbolInfo?conId=123` - Get contract details

### Advanced
- `GET /dynamic/{method_path}` - Direct IB API method calls

### Example Usage

```javascript
// Check connection
fetch('http://localhost:3005/health')
  .then(res => res.json())
  .then(data => console.log('Connected:', data.ib_connected));

// Get accounts
fetch('http://localhost:3005/accounts')
  .then(res => res.json())
  .then(accounts => console.log(accounts));

// Search for Apple stock
fetch('http://localhost:3005/search?symbol=AAPL')
  .then(res => res.json())
  .then(contracts => console.log(contracts));

// Load 1-minute candles
fetch('http://localhost:3005/loadData?conId=265598&interval=1min&limit=100')
  .then(res => res.json())
  .then(candles => console.log(candles));
```

## Troubleshooting

### Common Issues

**"Failed to connect to IB Gateway"**
- Ensure IB Gateway/TWS is running
- Check API settings are enabled
- Verify correct port (7497 for Gateway, 7496 for TWS)
- Try different client ID if multiple connections

**"Connection refused"**
- Check firewall settings
- Ensure IB Gateway allows API connections
- Verify host/port configuration

**"CORS errors in browser"**
- This proxy solves CORS issues
- Ensure you're connecting to the proxy (port 3005) not IB directly (port 7497)

**"Executable not available for my platform"**
- Use Python directly: `python main.py`
- All platforms support Python installation
- Executables are convenience, not requirement

### Logging

The proxy provides detailed logging. For more verbose output:
```bash
# Enable debug logging
export PYTHONPATH=.
python -c "import logging; logging.basicConfig(level=logging.DEBUG)" main.py
```

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests if applicable
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- **Issues**: Report bugs via GitHub Issues
- **Discussions**: Use GitHub Discussions for questions
- **IB API**: Refer to [Interactive Brokers API documentation](https://interactivebrokers.github.io/tws-api/)

## Disclaimer

This software is for educational and development purposes. Use at your own risk. Not affiliated with Interactive Brokers.