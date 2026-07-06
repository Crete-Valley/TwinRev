import requests
from typing import Any, Dict, List, Optional

class EnergyForecastingClient:
    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.session.headers.update({"Content-Type": "application/json"})

    # ---------------------------
    # Health Check
    # ---------------------------
    def health(self) -> Dict[str, Any]:
        url = f"{self.base_url}/health"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    # ---------------------------
    # Models
    # ---------------------------
    def list_models(self) -> Dict[str, Any]:
        url = f"{self.base_url}/models/"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def clear_cache(self) -> Dict[str, Any]:
        url = f"{self.base_url}/models/"
        response = self.session.delete(url)
        response.raise_for_status()
        return response.json()

    def load_model(self, model_name: str, uri: Optional[str] = None, config: Optional[Dict] = None, force_reload: bool = False) -> Dict[str, Any]:
        url = f"{self.base_url}/models/{model_name}/load"
        payload = {
            "uri": uri,
            "config": config,
            "force_reload": force_reload
        }
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def unload_model(self, model_name: str, uri: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/models/{model_name}"
        params = {"uri": uri} if uri else None
        response = self.session.delete(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        url = f"{self.base_url}/models/{model_name}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_model_window(self, model_name: str, uri: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/models/{model_name}/window"
        params = {"uri": uri} if uri else None
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def list_mlflow_models(self) -> Dict[str, Any]:
        url = f"{self.base_url}/models/mlflow/registered"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    # ---------------------------
    # Forecasting
    # ---------------------------
    def create_forecast(
        self,
        model_name: str,
        data: Dict[str, Any],
        horizon: int,
        model_uri: Optional[str] = None,
        config: Optional[Dict] = None,
        past_covariates: Optional[Dict[str, List[float]]] = None,
        future_covariates: Optional[Dict[str, List[float]]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/forecast/"
        data_payload = dict(data)
        if past_covariates is not None:
            data_payload["past_covariates"] = past_covariates
        if future_covariates is not None:
            data_payload["future_covariates"] = future_covariates
        payload = {
            "model_name": model_name,
            "data": data_payload,
            "horizon": horizon,
            "model_uri": model_uri,
            "config": config,
        }
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def create_batch_forecast(self, data: Dict[str, Any], horizon: int, models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/forecast/batch"
        payload = {
            "data": data,
            "horizon": horizon,
            "models": models
        }
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    
# Initialize client
# client = EnergyForecastingClient(token="")

# # Check API health
# health = client.health()
# print("Service status:", health["status"])

# # List all models
# models = client.list_models()
# print("Available models:", models)

# # Load a model
# client.load_model("chronos", uri="amazon/chronos-bolt-small")

# # Forecast example
# forecast = client.create_forecast(
#     model_name="chronos",
#     data={"timestamps": ["2024-01-01T00:00:00","2024-01-01T01:00:00","2024-01-01T02:00:00"], "values": [100.5,102.3,103.7]},
#     horizon=24
# )
# print("Forecast:", forecast)

# sample forecast response:
# {
#   "forecast": [
#     103,
#     103,
#     103,
#     103,
#     103,
#     102.5,
#     102.5,
#     102.5,
#     102.5,
#     102,
#     102.5,
#     102.5,
#     102,
#     102,
#     102.5,
#     102.5,
#     102,
#     102,
#     102,
#     102,
#     101.5,
#     102,
#     102.5,
#     102.5
#   ],
#   "timestamps": [
#     "2024-01-01T03:00:00",
#     "2024-01-01T04:00:00",
#     "2024-01-01T05:00:00",
#     "2024-01-01T06:00:00",
#     "2024-01-01T07:00:00",
#     "2024-01-01T08:00:00",
#     "2024-01-01T09:00:00",
#     "2024-01-01T10:00:00",
#     "2024-01-01T11:00:00",
#     "2024-01-01T12:00:00",
#     "2024-01-01T13:00:00",
#     "2024-01-01T14:00:00",
#     "2024-01-01T15:00:00",
#     "2024-01-01T16:00:00",
#     "2024-01-01T17:00:00",
#     "2024-01-01T18:00:00",
#     "2024-01-01T19:00:00",
#     "2024-01-01T20:00:00",
#     "2024-01-01T21:00:00",
#     "2024-01-01T22:00:00",
#     "2024-01-01T23:00:00",
#     "2024-01-02T00:00:00",
#     "2024-01-02T01:00:00",
#     "2024-01-02T02:00:00"
#   ],
#   "confidence_intervals": {
#     "lower": [
#       99,
#       97.5,
#       97,
#       96.5,
#       95.5,
#       95,
#       95,
#       94.5,
#       94,
#       93.5,
#       93.5,
#       93.5,
#       93,
#       92.5,
#       93,
#       93,
#       93,
#       92.5,
#       92.5,
#       92.5,
#       92,
#       92,
#       92.5,
#       92.5
#     ],
#     "upper": [
#       109,
#       111.5,
#       114.5,
#       116.5,
#       117.5,
#       118.5,
#       119.5,
#       120,
#       120.5,
#       120.5,
#       121,
#       121.5,
#       121.5,
#       121.5,
#       121.5,
#       121.5,
#       121,
#       120.5,
#       120.5,
#       120.5,
#       120,
#       120.5,
#       121.5,
#       121.5
#     ],
#     "level": [
#       0.1,
#       0.9
#     ]
#   },
#   "model_name": "chronos",
#   "metadata": {
#     "model_type": "chronos",
#     "model_family": "bolt",
#     "model_size": "small",
#     "num_samples": null,
#     "probabilistic": true,
#     "inference_time_ms": 15.06
#   }
# }