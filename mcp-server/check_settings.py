from lrc_client import LrCClient

c = LrCClient()
r = c.send_command("get_develop_settings")
s = r["result"]["photos"][0]["settings"]

print("Settings applied:")
print(f"  Exposure: {s.get('Exposure2012')}")
print(f"  Contrast: {s.get('Contrast2012')}")
print(f"  Shadows: {s.get('Shadows2012')}")
print(f"  Highlights: {s.get('Highlights2012')}")
print(f"  Whites: {s.get('Whites2012')}")
print(f"  Blacks: {s.get('Blacks2012')}")
print(f"  Texture: {s.get('Texture')}")
print(f"  Clarity: {s.get('Clarity2012')}")
print(f"  Dehaze: {s.get('Dehaze')}")
print(f"  Vibrance: {s.get('Vibrance')}")
print(f"  Saturation: {s.get('Saturation')}")
print(f"  Sharpness: {s.get('Sharpness')}")
print(f"  Vignette: {s.get('PostCropVignetteAmount')}")
