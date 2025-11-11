import os

os.getenv("USE_LOCAL_EXCHANGE", "False")
print(os.getenv("USE_LOCAL_EXCHANGE", "False"))
print(os.getenv("USE_MOCK_DATA"))