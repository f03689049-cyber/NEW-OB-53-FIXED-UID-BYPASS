import codecs

def encode_string(original):
    """Encode string with XOR encryption"""
    keystream = [
        0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37, 0x30,
        0x30, 0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37,
        0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30, 0x31,
        0x37, 0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30
    ]
    encoded = ""
    for i in range(len(original)):
        orig_byte = ord(original[i])
        key_byte = keystream[i % len(keystream)]
        result_byte = orig_byte ^ key_byte
        encoded += chr(result_byte)

    return {
        "open_id": original,
        "field_14": encoded
    }

def to_unicode_escaped(s):
    """Convert string to Python-style Unicode escaped string"""
    return ''.join(
        c if 32 <= ord(c) <= 126 else f'\\u{ord(c):04x}'
        for c in s
    )