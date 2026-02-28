import urllib.request
import json

url = "http://127.0.0.1:8081/api/openalex/works/?q=machine+learning&per_page=5"
try:
    with urllib.request.urlopen(url) as response:
        data = response.read().decode()
        print("Status:", response.status)
        print("Response:")
        print(data)
except Exception as e:
    print("Error:", e)
