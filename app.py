from flask import Flask, render_template, request, jsonify, session
import requests
import zlib
import os
import json
import re
from waitress import serve

app = Flask(__name__)
app.secret_key = "supersecretkey"   

# Endpoints to be used for the code of this ai agent explorer.
ACCOUNT_MODULES_URL = "https://rpc-testnet.supra.com/rpc/v2/accounts/{address}/modules"
ACCOUNT_RESOURCES_URL = "https://rpc-testnet.supra.com/rpc/v1/accounts/{address}/resources/0x1::code::PackageRegistry"
ALL_RESOURCES_URL = "https://rpc-testnet.supra.com/rpc/v3/accounts/{address}/resources"
TRANSFER_STATS_URL = "https://services.blockpour.com/query/stats/supra/transfer-stats"
RECENT_TRANSFERS_URL = "https://services.blockpour.com/query/transfers/recent-supra?limit={limit}"
 
# pkg reg for using to fetch the module source code. 
def get_package_registry(address: str) -> dict:
    """Get package registry for an address"""
    url = ACCOUNT_RESOURCES_URL.format(address=address)
    try:
        response = requests.get(url, timeout=10)
        return response.json() if response.status_code == 200 else {"error": response.text}
    except requests.RequestException as e:
        return {"error": f"Network error: {str(e)}"}

# ref taken from Nolan's code of fetching module code also available on suprascan.
def extract_module_source(mod_source: str) -> str:
    """Extract and decompress module source code"""
    if mod_source == "0x":
        return "No source text published."
    
    try:
        hex_str = mod_source[2:]
        buffer = bytes.fromhex(hex_str)
        source_text = zlib.decompress(buffer, 16 + zlib.MAX_WBITS)
        return source_text.decode('utf-8')
    except Exception as e:
        return f"Error decompressing source: {e}"
    
# use the REST API given in our official docs to fetch modules.
def list_modules(address: str) -> list:
    """List all modules deployed at an address using the correct modules endpoint"""
    url = f"https://rpc-testnet.supra.com/rpc/v2/accounts/{address}/modules"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            modules = []
            
 
            if "modules" in data and isinstance(data["modules"], list):
                for module in data["modules"]:
                    if "abi" in module and "name" in module["abi"]:
                        module_name = module["abi"]["name"]
                        if module_name not in modules:
                            modules.append(module_name)
            
            return modules
        else:
            return {"error": response.text}
    except requests.RequestException as e:
        return {"error": f"Network error: {str(e)}"}

# use the code ref given in dev-adv to fetch module code.
def get_module_source_by_name(address: str, module_name: str) -> str:
    """Get source code for a specific module using PackageRegistry like the JavaScript example"""
    url = f"https://rpc-testnet.supra.com/rpc/v1/accounts/{address}/resources/0x1::code::PackageRegistry"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()  
            if "result" in data and isinstance(data["result"], list) and len(data["result"]) > 0:
                registry = data["result"][0]
                if "packages" in registry:
                    for package in registry["packages"]:
                        if "modules" in package:
                            for module in package["modules"]:
                                if "name" in module and module["name"].lower() == module_name.lower():
                                    if "source" in module:
                                        return extract_module_source(module["source"])
                                    else:
                                        return "No source field found for this module."
            return f"Module '{module_name}' not found in PackageRegistry."
        else:
            return f"Error fetching PackageRegistry: HTTP {response.status_code} - {response.text}"
    except requests.RequestException as e:
        return f"Network error: {str(e)}"
    except Exception as e:
        return f"Error retrieving module source: {str(e)}"

# use the REST API given in our official docs to fetch resources.
def get_all_resources(address: str) -> dict:
    """Get all resources deployed at an address"""
    url = ALL_RESOURCES_URL.format(address=address)
    try:
        response = requests.get(url, timeout=10)
        return response.json() if response.status_code == 200 else {"error": response.text}
    except requests.RequestException as e:
        return {"error": f"Network error: {str(e)}"}

# Endpoints from OpenBlocks.ai to get onchain transfer statistics and recent transfers.
def get_transfer_stats() -> dict:
    """Get transfer statistics for SUPRA token"""
    try:
        response = requests.get(TRANSFER_STATS_URL, timeout=10)
        return response.json() if response.status_code == 200 else {"error": response.text}
    except requests.RequestException as e:
        return {"error": f"Network error: {str(e)}"}

def get_recent_transfers(limit: int = 50) -> dict:
    """Get recent on-chain transfers"""
    url = RECENT_TRANSFERS_URL.format(limit=limit)
    try:
        response = requests.get(url, timeout=10)
        return response.json() if response.status_code == 200 else {"error": response.text}
    except requests.RequestException as e:
        return {"error": f"Network error: {str(e)}"}

# pckge it all together in a function to process user commands.
def process_command(command: str) -> str:
    """
    Parse the user's command and return a formatted response.
    Enhanced with better error handling and formatting.
    """
    command = command.lower().strip()
 
    if command in ["help", "options", "menu"]:
        return """🚀 Supra Explorer Agent - Command Reference

📋 AVAILABLE COMMANDS:

1️⃣ LIST MODULES
   Usage: list modules at <address>
   Example: list modules at 0x1
   
2️⃣ GET MODULE SOURCE CODE
   Usage: get module code at <address>
   Then: choose module <name or index>
   OR: get module code of <module> at <address>
   
3️⃣ LIST RESOURCES  
   Usage: list resources at <address>
   Example: list resources at 0x1
   
4️⃣ TRANSFER STATISTICS
   Usage: transfer stats
   
5️⃣ RECENT TRANSFERS
   Usage: recent onchain transfers with limit <number>
   Example: recent onchain transfers with limit 10

💡 I can help you explore the Supra blockchain, analyze smart contracts,
   and retrieve on-chain data with these commands.

Type any command to get started! 🎯"""

    if "get module code of" in command:
        match = re.search(r"get module code of ([^\s]+) at ([^\s]+)", command)
        if match:
            module = match.group(1)
            address = match.group(2)
            try:
                code = get_module_source_by_name(address, module)
                return f"📄 Source code for module '{module}' at {address}:\n\n```move\n{code}\n```"
            except Exception as e:
                return f"❌ Error retrieving module source: {str(e)}"
        return "❌ Usage: get module code of <module> at <address>"
    
    if command.startswith("get module code at"):
        match = re.search(r"get module code at ([^\s]+)", command)
        if match:
            address = match.group(1)
            try:
                modules = list_modules(address)
                if isinstance(modules, dict) and "error" in modules:
                    return f"❌ Error: {modules['error']}"
                
                if not modules:
                    return f"📭 No modules found at address {address}"
                
                session["pending_module"] = {"address": address, "modules": modules}
                mod_list_str = "\n".join(f"  {i+1:2d}. {mod}" for i, mod in enumerate(modules))
                return f"📦 Modules at {address}:\n\n{mod_list_str}\n\n💡 Type 'choose module <name or number>' to view source code"
            except Exception as e:
                return f"❌ Error retrieving modules: {str(e)}"
        return "❌ Usage: get module code at <address>"
 
    if command.startswith("choose module"):
        if "pending_module" not in session:
            return "❌ No module selection pending. Use 'get module code at <address>' first."
        
        match = re.search(r"choose module (.+)", command)
        if match:
            selection = match.group(1).strip()
            pending = session["pending_module"]
            address = pending.get("address")
            modules = pending.get("modules", [])
            
            selected_module = None
 
            if selection.isdigit():
                index = int(selection) - 1
                if 0 <= index < len(modules):
                    selected_module = modules[index]
            else:
 
                for module in modules:
                    if module.lower() == selection.lower():
                        selected_module = module
                        break
            
            if selected_module:
                try:
                    code = get_module_source_by_name(address, selected_module)
                    session.pop("pending_module", None)
                    return f"📄 Source code for '{selected_module}':\n\n```move\n{code}\n```"
                except Exception as e:
                    return f"❌ Error retrieving source: {str(e)}"
            else:
                return f"❌ Invalid selection '{selection}'. Please use a valid number or module name."
        return "❌ Usage: choose module <name or number>"

 
    if "list modules" in command:
        match = re.search(r"list modules at ([^\s]+)", command)
        if match:
            address = match.group(1)
            try:
                modules = list_modules(address)
                if isinstance(modules, dict) and "error" in modules:
                    return f"❌ Error: {modules['error']}"
                
                if not modules:
                    return f"📭 No modules found at address {address}"
 
                mod_list = "\n".join(f"  • {mod}" for mod in modules)
                return f"📦 Modules deployed at {address}:\n\n{mod_list}\n\n💡 Use 'get module code of <module> at {address}' to view source"
            except Exception as e:
                return f"❌ Error: {str(e)}"
        return "❌ Usage: list modules at <address>"
 
    elif "list resources" in command:
        match = re.search(r"list resources at ([^\s]+)", command)
        if match:
            address = match.group(1)
            try:
                resources = get_all_resources(address)
                if isinstance(resources, dict) and "error" in resources:
                    return f"❌ Error: {resources['error']}"
                
                return f"🗂️ Resources at {address}:\n\n{json.dumps(resources, indent=2)}"
            except Exception as e:
                return f"❌ Error: {str(e)}"
        return "❌ Usage: list resources at <address>"
 
    elif "transfer stats" in command:
        try:
            stats = get_transfer_stats()
            if isinstance(stats, dict) and "error" in stats:
                return f"❌ Error: {stats['error']}"
            return f"📊 SUPRA Transfer Statistics:\n\n{json.dumps(stats, indent=2)}"
        except Exception as e:
            return f"❌ Error: {str(e)}"
 
    elif "recent onchain transfers" in command:
        match = re.search(r"recent onchain transfers(?: with limit (\d+))?", command)
        limit = 10  
        if match and match.group(1):
            try:
                limit = int(match.group(1))
                limit = min(limit, 100)  
            except:
                pass
        
        try:
            transfers = get_recent_transfers(limit)
            if isinstance(transfers, dict) and "error" in transfers:
                return f"❌ Error: {transfers['error']}"
            return f"🔄 Recent On-Chain Transfers (limit: {limit}):\n\n{json.dumps(transfers, indent=2)}"
        except Exception as e:
            return f"❌ Error: {str(e)}"
    elif command == "exit":
        return "👋 Session ended. Refresh the page to restart."
    else:
        return f"""❌ Unknown command: '{command}'

💡 Type 'help' to see all available commands, or try:
• list modules at 0x1
• transfer stats  
• recent onchain transfers with limit 10"""
 
@app.route("/")
def index():
    """Serve the main page"""
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    """Handle chat requests with enhanced error handling"""
    try:
        user_message = request.json.get("message", "").strip()
        if not user_message:
            return jsonify({"response": "❌ Please enter a command"})
        
        response_text = process_command(user_message)
        return jsonify({"response": response_text})
    
    except Exception as e:
        return jsonify({
            "response": f"❌ Internal error: {str(e)}\n\nPlease try again or type 'help' for available commands."
        })

@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "Supra Explorer Agent"})

if __name__ == "__main__":
    print("🚀 Starting Supra Explorer Agent...")
    print("📡 Endpoints configured for Supra Testnet")
    print("🌐 Server will be available at http://localhost:5000")
    serve(app, host="0.0.0.0", port=5000)