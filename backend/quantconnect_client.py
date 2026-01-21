"""
QuantConnect API Client
Handles all interactions with QuantConnect's REST API
"""

import os
import asyncio
import hashlib
import time
from typing import Optional
import httpx


class QuantConnectClient:
    """
    Async client for QuantConnect API
    
    Requires environment variables:
    - QC_USER_ID: Your QuantConnect user ID
    - QC_API_TOKEN: Your API token
    """
    
    BASE_URL = "https://www.quantconnect.com/api/v2"
    
    def __init__(self):
        self.user_id = os.environ.get("QC_USER_ID")
        self.api_token = os.environ.get("QC_API_TOKEN")
        
        if not self.user_id or not self.api_token:
            raise ValueError(
                "QC_USER_ID and QC_API_TOKEN environment variables required"
            )
        
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client
    
    def _get_auth_headers(self) -> dict:
        """Generate authentication headers"""
        timestamp = str(int(time.time()))
        
        # QC uses hash-based auth
        hash_string = f"{self.api_token}:{timestamp}"
        hash_bytes = hashlib.sha256(hash_string.encode()).hexdigest()
        
        return {
            "Timestamp": timestamp,
            "Authorization": f"Basic {self.user_id}:{hash_bytes}"
        }
    
    async def _request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[dict] = None
    ) -> dict:
        """Make authenticated API request"""
        url = f"{self.BASE_URL}/{endpoint}"
        headers = self._get_auth_headers()
        
        if method == "GET":
            response = await self.client.get(url, headers=headers, params=data)
        else:
            response = await self.client.post(url, headers=headers, json=data)
        
        response.raise_for_status()
        return response.json()
    
    async def list_projects(self) -> list[dict]:
        """List all projects"""
        result = await self._request("GET", "projects/read")
        return result.get("projects", [])
    
    async def get_project(self, project_id: str) -> dict:
        """Get project details"""
        result = await self._request("GET", "projects/read", {
            "projectId": project_id
        })
        return result.get("projects", [{}])[0]
    
    async def create_project(self, name: str, language: str = "Py") -> dict:
        """Create a new project"""
        result = await self._request("POST", "projects/create", {
            "name": name,
            "language": language
        })
        return result.get("projects", [{}])[0]
    
    async def update_file(
        self, 
        project_id: str, 
        filename: str, 
        content: str
    ) -> bool:
        """Update a file in the project"""
        result = await self._request("POST", "files/update", {
            "projectId": project_id,
            "name": filename,
            "content": content
        })
        return result.get("success", False)
    
    async def compile_project(
        self, 
        project_id: str, 
        code: Optional[str] = None
    ) -> dict:
        """
        Compile a project
        Optionally update main.py before compiling
        """
        # Update code if provided
        if code:
            await self.update_file(project_id, "main.py", code)
        
        result = await self._request("POST", "compile/create", {
            "projectId": project_id
        })
        
        if not result.get("success"):
            return {"success": False, "errors": result.get("errors", [])}
        
        compile_id = result.get("compileId")
        
        # Poll for compilation completion
        for _ in range(30):  # Max 30 seconds
            status = await self._request("GET", "compile/read", {
                "projectId": project_id,
                "compileId": compile_id
            })
            
            state = status.get("state", "")
            
            if state == "BuildSuccess":
                return {
                    "success": True,
                    "compileId": compile_id
                }
            elif state == "BuildError":
                return {
                    "success": False,
                    "errors": status.get("errors", [])
                }
            
            await asyncio.sleep(1)
        
        return {"success": False, "errors": ["Compilation timeout"]}
    
    async def create_backtest(
        self, 
        project_id: str, 
        compile_id: str, 
        name: str
    ) -> str:
        """Create and start a backtest"""
        result = await self._request("POST", "backtests/create", {
            "projectId": project_id,
            "compileId": compile_id,
            "backtestName": name
        })
        
        return result.get("backtestId", "")
    
    async def get_backtest(self, project_id: str, backtest_id: str) -> dict:
        """Get backtest results"""
        result = await self._request("GET", "backtests/read", {
            "projectId": project_id,
            "backtestId": backtest_id
        })
        return result.get("backtest", {})
    
    async def wait_for_backtest(
        self, 
        backtest_id: str,
        project_id: Optional[str] = None,
        timeout: int = 300
    ) -> Optional[dict]:
        """
        Poll until backtest completes
        Returns results or None on timeout
        """
        start = time.time()
        
        while time.time() - start < timeout:
            result = await self.get_backtest(project_id, backtest_id)
            
            if result.get("completed"):
                # Extract key metrics
                return {
                    "backtestId": backtest_id,
                    "sharpeRatio": result.get("sharpeRatio", 0),
                    "drawdown": result.get("drawdown", 0),
                    "totalPerformance": result.get("totalPerformance", 0),
                    "winRate": result.get("statistics", {}).get("Win Rate", "0%"),
                    "totalNumberOfTrades": result.get("totalOrders", 0),
                    "averageTradeDuration": result.get("statistics", {}).get(
                        "Average Trade Duration", "0"
                    ),
                    "raw": result
                }
            
            await asyncio.sleep(5)
        
        return None
    
    async def delete_backtest(self, project_id: str, backtest_id: str) -> bool:
        """Delete a backtest"""
        result = await self._request("POST", "backtests/delete", {
            "projectId": project_id,
            "backtestId": backtest_id
        })
        return result.get("success", False)
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
