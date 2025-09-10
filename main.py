from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from ib_insync import IB, Contract
import logging
import asyncio
import argparse
import json
from contextlib import asynccontextmanager
from typing import Dict, Set

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Reduce ib_insync logging noise
logging.getLogger('ib_insync').setLevel(logging.WARNING)

# Global configuration
config = {
    'ib_host': '127.0.0.1',
    'ib_port': 7497,
    'proxy_host': '127.0.0.1', 
    'proxy_port': 3005,
    'client_id': 1
}

ib = IB()

# Global subscription manager
class SubscriptionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.price_subscriptions: Dict[int, Contract] = {}
        self.candle_subscriptions: Dict[int, tuple] = {}
        self.listeners_setup = False
    
    async def connect(self, websocket: WebSocket, subscription_type: str):
        await websocket.accept()
        if subscription_type not in self.active_connections:
            self.active_connections[subscription_type] = set()
        self.active_connections[subscription_type].add(websocket)
    
    def disconnect(self, websocket: WebSocket, subscription_type: str):
        if subscription_type in self.active_connections:
            self.active_connections[subscription_type].discard(websocket)
    
    async def broadcast(self, subscription_type: str, data: dict):
        if subscription_type in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[subscription_type]:
                try:
                    await connection.send_text(json.dumps(data))
                except:
                    disconnected.add(connection)
            for conn in disconnected:
                self.active_connections[subscription_type].discard(conn)
    


manager = SubscriptionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not ib.isConnected():
        try:
            logger.info(f"Connecting to IB Gateway at {config['ib_host']}:{config['ib_port']} with client ID {config['client_id']}")
            await ib.connectAsync(config['ib_host'], config['ib_port'], clientId=config['client_id'])
            logger.info(f"Successfully connected to IB Gateway")
        except Exception as e:
            logger.error(f"Failed to connect to IB Gateway: {e}")
            logger.error("Make sure TWS or IB Gateway is running and API connections are enabled")
    
    yield
    
    # Shutdown
    if ib.isConnected():
        ib.disconnect()
        logger.info("Disconnected from IB Gateway")

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/accounts")
async def get_accounts():
    if not ib.isConnected():
        raise HTTPException(status_code=503, detail="Not connected")
    accounts = ib.managedAccounts()
    return {"accounts": [{"id": acc, "accountId": acc} for acc in accounts]}

@app.get("/positions/{account_id}")
async def get_positions(account_id: str):
    if not ib.isConnected():
        raise HTTPException(status_code=503, detail="Not connected")
    
    positions = ib.positions(account_id)

    return positions

@app.get("/search")
async def search_contracts(symbol: str):
    if not ib.isConnected():
        raise HTTPException(status_code=503, detail="Not connected")
    
    try:
        logger.info(f"Searching for symbol: {symbol}")
        
        # Search for exact match and partial matches
        search_patterns = [symbol.upper()]
        if len(symbol) <= 3:  # For short symbols, add wildcard patterns
            search_patterns.extend([symbol.upper() + "*", symbol.upper() + "?"])
        
        all_results = []
        seen_conids = set()
        
        for pattern in search_patterns:
            try:
                contracts = await ib.reqMatchingSymbolsAsync(pattern)
                
                for contract_desc in contracts:
                    contract = contract_desc.contract
                    if contract.conId not in seen_conids:
                        seen_conids.add(contract.conId)
                        all_results.append(contract)
        
            except Exception as e:
                logger.error(f"Pattern {pattern} failed: {e}")
                continue
        
        logger.info(f"Found {len(all_results)} unique contracts")
        return all_results
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

@app.get("/dynamic/{method_path:path}")
async def dynamic_call(method_path: str, request: Request):
    if not ib.isConnected():
        raise HTTPException(status_code=503, detail="Not connected")
    
    try:
        # Log the method call
        params = dict(request.query_params)
        logger.info(f"Dynamic call: {method_path} with params: {params}")
        
        # Parse method path (e.g., "reqContractDetails" or "client.getReqId")
        method_parts = method_path.split('.')
        
        # Start with ib object
        obj = ib
        
        # Navigate through nested attributes
        for part in method_parts[:-1]:
            obj = getattr(obj, part)
        
        # Get the final method
        method_name = method_parts[-1]
        method = getattr(obj, method_name)
        
        # Convert string params to appropriate types
        converted_params = {}
        for key, value in params.items():
            # Try to convert to int, float, or keep as string
            try:
                if '.' in value:
                    converted_params[key] = float(value)
                else:
                    converted_params[key] = int(value)
            except ValueError:
                converted_params[key] = value
        
        logger.info(f"Calling {method_name} with converted params: {converted_params}")
        
        # Call the method
        if hasattr(method, '__call__'):
            if asyncio.iscoroutinefunction(method):
                result = await method(**converted_params)
            else:
                result = method(**converted_params)
        else:
            # It's a property, not a method
            result = method
        
        logger.info(f"Method {method_name} returned: {type(result)} with {len(result) if hasattr(result, '__len__') else 'N/A'} items")
        return {"result": result, "method": method_path, "params": converted_params}
        
    except AttributeError as e:
        logger.error(f"AttributeError for {method_path}: {e}")
        raise HTTPException(status_code=404, detail=f"Method {method_path} not found")
    except Exception as e:
        logger.error(f"Error calling {method_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Error calling {method_path}: {str(e)}")

@app.get("/loadData")
async def load_data(conId: int, interval: str, limit: int = 100, duration: str = None):
    if not ib.isConnected():
        raise HTTPException(status_code=503, detail="Not connected")
    
    try:
        logger.info(f"Loading data for conId={conId}, interval={interval}, limit={limit}")
        
        from ib_insync import Contract
        import datetime
        contract = Contract()
        contract.conId = conId
        
        # Get full contract details first
        contract_details = await ib.reqContractDetailsAsync(contract)
        if not contract_details:
            logger.error(f"No contract details found for conId {conId}")
            return []
            
        full_contract = contract_details[0].contract
        logger.info(f"Full contract: {full_contract}")
        
        # Use the already mapped values
        bar_size = interval
        
        # Use provided duration or default to 1 D
        if not duration:
            duration = '1 D'
        
        logger.info(f"Requesting historical data: duration={duration}, barSize={bar_size}")
        
        bars = await ib.reqHistoricalDataAsync(
            full_contract, endDateTime='', durationStr=duration,
            barSizeSetting=bar_size, whatToShow='TRADES', useRTH=False
        )
        
        logger.info(f"Received {len(bars)} bars")
        
        result = []
        for bar in bars:
            if hasattr(bar.date, 'timestamp'):
                timestamp = int(bar.date.timestamp())
            else:
                dt = datetime.datetime.combine(bar.date, datetime.time())
                timestamp = int(dt.timestamp())
                
            result.append({
                'time': timestamp,
                'open': float(bar.open),
                'high': float(bar.high),
                'low': float(bar.low),
                'close': float(bar.close),
                'volume': float(bar.volume)
            })
        
        logger.info(f"Returning {len(result)} candles")
        return result
        
    except Exception as e:
        logger.error(f"Load data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/loadMoreData")
async def load_more_data(conId: int, interval: str, limit: int = 100, endTime: int = None, duration: str = None):
    if not ib.isConnected():
        raise HTTPException(status_code=503, detail="Not connected")
    
    try:
        logger.info(f"Loading more data for conId={conId}, interval={interval}, limit={limit}, endTime={endTime}")
        
        from ib_insync import Contract
        import datetime
        
        contract = Contract()
        contract.conId = conId
        
        # Get full contract details first
        contract_details = await ib.reqContractDetailsAsync(contract)
        if not contract_details:
            logger.error(f"No contract details found for conId {conId}")
            return []
            
        full_contract = contract_details[0].contract
        
        # Use the already mapped values
        bar_size = interval
        
        # Use provided duration or default to 1 D
        if not duration:
            duration = '1 D'
            
        # Convert endTime to datetime string if provided
        end_date_time = ''
        if endTime:
            dt = datetime.datetime.fromtimestamp(endTime)
            # Always use full datetime format for IB compatibility
            end_date_time = dt.strftime('%Y%m%d %H:%M:%S')
            logger.info(f"Using endDateTime: {end_date_time}")
        
        logger.info(f"Requesting historical data: duration={duration}, barSize={bar_size}, endDateTime='{end_date_time}'")
        
        bars = await ib.reqHistoricalDataAsync(
            full_contract, endDateTime=end_date_time, durationStr=duration,
            barSizeSetting=bar_size, whatToShow='TRADES', useRTH=False
        )
        
        logger.info(f"Received {len(bars)} bars")
        
        result = []
        for bar in bars:
            if hasattr(bar.date, 'timestamp'):
                timestamp = int(bar.date.timestamp())
            else:
                dt = datetime.datetime.combine(bar.date, datetime.time())
                timestamp = int(dt.timestamp())
                
            result.append({
                'time': timestamp,
                'open': float(bar.open),
                'high': float(bar.high),
                'low': float(bar.low),
                'close': float(bar.close),
                'volume': float(bar.volume)
            })
        
        logger.info(f"Returning {len(result)} candles")
        return result
        
    except Exception as e:
        logger.error(f"Load more data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/getSymbolInfo")
async def get_symbol_info(conId: int):
    if not ib.isConnected():
        raise HTTPException(status_code=503, detail="Not connected")
    
    try:
        from ib_insync import Contract
        contract = Contract()
        contract.conId = conId
        
        details = await ib.reqContractDetailsAsync(contract)
        if not details:
            return None
            
        detail = details[0]
        return detail
        
    except Exception as e:
        logger.error(f"Symbol info error: {e}")
        return None

@app.websocket("/ws/price/{conid}")
async def websocket_price(websocket: WebSocket, conid: int):
    await manager.connect(websocket, f"price_{conid}")
    
    try:
        contract = Contract()
        contract.conId = conid
        contract_details = await ib.reqContractDetailsAsync(contract)
        if not contract_details:
            await websocket.close()
            return
        full_contract = contract_details[0].contract
        
        ticker = ib.reqMktData(full_contract, '', False, False)
        
        def onPendingTickers(tickers):
            for t in tickers:
                if t.contract.conId == conid:
                    asyncio.create_task(manager.broadcast(f"price_{conid}", {
                        "type": "price", "conId": conid,
                        "price": float(t.last) if t.last else 0,
                        "bid": float(t.bid) if t.bid else 0,
                        "ask": float(t.ask) if t.ask else 0,
                        "volume": float(t.volume) if t.volume else 0
                    }))
        
        ib.pendingTickersEvent += onPendingTickers
        
        while True:
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"price_{conid}")
        ib.cancelMktData(full_contract)
        ib.pendingTickersEvent -= onPendingTickers

@app.websocket("/ws/candles/{conid}/{interval}")
async def websocket_candles(websocket: WebSocket, conid: int, interval: str):
    await manager.connect(websocket, f"candles_{conid}_{interval}")
    
    try:
        contract = Contract()
        contract.conId = conid
        contract_details = await ib.reqContractDetailsAsync(contract)
        if not contract_details:
            await websocket.close()
            return
        full_contract = contract_details[0].contract
        
        def onBarUpdate(bars, hasNewBar):
            if hasNewBar and bars:
                bar = bars[-1]
                asyncio.create_task(manager.broadcast(f"candles_{conid}_{interval}", {
                    "type": "candle", "conId": conid,
                    "time": int(bar.time.timestamp()),
                    "open": float(bar.open_), "high": float(bar.high),
                    "low": float(bar.low), "close": float(bar.close),
                    "volume": float(bar.volume)
                }))
        
        bars = ib.reqRealTimeBars(full_contract, 5, 'TRADES', False)
        bars.updateEvent += onBarUpdate
        
        while True:
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"candles_{conid}_{interval}")
        ib.cancelRealTimeBars(full_contract)

@app.websocket("/ws/orderbook/{conid}")
async def websocket_orderbook(websocket: WebSocket, conid: int):
    await manager.connect(websocket, f"orderbook_{conid}")
    
    try:
        contract = Contract()
        contract.conId = conid
        contract_details = await ib.reqContractDetailsAsync(contract)
        if not contract_details:
            await websocket.close()
            return
        full_contract = contract_details[0].contract
        
        ticker = ib.reqMktData(full_contract, '', False, False)
        
        def onPendingTickers(tickers):
            for t in tickers:
                if t.contract.conId == conid:
                    asyncio.create_task(manager.broadcast(f"orderbook_{conid}", {
                        "type": "orderbook",
                        "bids": [{"price": float(t.bid), "quantity": float(t.bidSize)}] if t.bid else [],
                        "asks": [{"price": float(t.ask), "quantity": float(t.askSize)}] if t.ask else []
                    }))
        
        ib.pendingTickersEvent += onPendingTickers
        
        while True:
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"orderbook_{conid}")
        ib.cancelMktData(full_contract)
        ib.pendingTickersEvent -= onPendingTickers

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "ib_connected": ib.isConnected(),
        "ib_host": config['ib_host'],
        "ib_port": config['ib_port'],
        "proxy_host": config['proxy_host'],
        "proxy_port": config['proxy_port']
    }

def parse_args():
    parser = argparse.ArgumentParser(description='IBKR Proxy Server - Bridges React apps to IB Gateway/TWS')
    parser.add_argument('--ib-host', default='127.0.0.1', help='IB Gateway/TWS host (default: 127.0.0.1)')
    parser.add_argument('--ib-port', type=int, default=7497, help='IB Gateway/TWS port (default: 7497 for Gateway, 7496 for TWS)')
    parser.add_argument('--proxy-host', default='127.0.0.1', help='Proxy server host (default: 127.0.0.1)')
    parser.add_argument('--proxy-port', type=int, default=3005, help='Proxy server port (default: 3005)')
    parser.add_argument('--client-id', type=int, default=1, help='IB API client ID (default: 1)')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    # Update global config
    config.update({
        'ib_host': args.ib_host,
        'ib_port': args.ib_port,
        'proxy_host': args.proxy_host,
        'proxy_port': args.proxy_port,
        'client_id': args.client_id
    })
    
    logger.info(f"Starting IBKR Proxy Server")
    logger.info(f"Proxy will run on: http://{config['proxy_host']}:{config['proxy_port']}")
    logger.info(f"Will connect to IB Gateway/TWS at: {config['ib_host']}:{config['ib_port']}")
    
    import uvicorn
    uvicorn.run(app, host=config['proxy_host'], port=config['proxy_port'])