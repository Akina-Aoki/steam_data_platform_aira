import requests

url = "https://store.steampowered.com/api/appdetails"
params = {"appids": 620, "cc": "se", "l": "english"}

response = requests.get(url, params=params, timeout=10)
print(response.status_code)

data = response.json()

print(type(data))
print(list(data.keys()))
print(data["620"]["success"])