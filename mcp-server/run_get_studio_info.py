from lrc_client import LrCClient
import json

def main():
    client = LrCClient()
    try:
        # print("Sending get_studio_info command...")
        response = client.send_command("get_studio_info")
        if response and "result" in response:
            print(json.dumps(response["result"], indent=2))
        elif response and "error" in response:
             print(f"Error from Lightroom: {response['error']}")
        else:
            print(f"Unexpected response: {response}")
    except Exception as e:
        print(f"Failed to execute command: {e}")

if __name__ == "__main__":
    main()
