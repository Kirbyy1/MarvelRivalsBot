import base64
import hashlib
import random
from datetime import datetime
from io import BytesIO
from Crypto.PublicKey import RSA



# --- Helper functions ---

def base10Encode(data: bytes) -> str:
    """Converts bytes into a base‑10 string representation of the big integer."""
    result = 0
    for b in data:
        result = result * 256 + b
    return str(result)


def base10Decode(number: int) -> bytes:
    """Converts a big integer into its byte representation (big‑endian)."""
    if number == 0:
        return b'\x00'
    result = bytearray()
    while number:
        number, rem = divmod(number, 256)
        result.insert(0, rem)
    return bytes(result)


def powmod(paramBase: str, paramExponent: str, paramModules: str) -> int:
    """Performs modular exponentiation: (base^exponent) mod modulus."""
    base = int(paramBase)
    exponent = int(paramExponent)
    modulus = int(paramModules)
    if modulus == 0:
        raise ValueError("Modulus is zero.")
    if exponent == 0:
        raise ValueError("Exponent is zero.")
    return pow(base, exponent, modulus)


def decodeSerial(data: bytes, public: str, modulus: str, expected_length: int) -> bytes:
    """
    "Decrypts" the license key using the RSA public parameters.
    Pads the result to expected_length bytes (to restore leading zeros).
    """
    tmpModules = base64.b64decode(modulus)
    tmpPublic = base64.b64decode(public)
    res = powmod(base10Encode(data), base10Encode(tmpPublic), base10Encode(tmpModules))
    result_bytes = base10Decode(res)
    # Left-pad with zeros if needed:
    if len(result_bytes) < expected_length:
        result_bytes = (b'\x00' * (expected_length - len(result_bytes))) + result_bytes
    return result_bytes


def filterSerial(serial: str) -> str:
    """Keeps only Base64 characters from the serial string."""
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
    return "".join(ch for ch in serial if ch in allowed)


# --- Packing/Unpacking License Data ---

def packSerial(lic: "License") -> bytes:
    """
    Packs license fields into a binary blob using a tag-length scheme.
    Tags (1-9) identify fields like version, name, email, etc.
    """
    buf = BytesIO()
    # Tag 1: Version (always 1)
    buf.write(bytes([1]))
    buf.write(bytes([1]))

    # Tag 2: Username
    if lic.name:
        name_bytes = lic.name.encode('utf-8')
        if len(name_bytes) > 255:
            raise ValueError("License->Name too long")
        buf.write(bytes([2]))
        buf.write(bytes([len(name_bytes)]))
        buf.write(name_bytes)

    # Tag 3: Email
    if lic.email:
        email_bytes = lic.email.encode('utf-8')
        if len(email_bytes) > 255:
            raise ValueError("License->Email too long")
        buf.write(bytes([3]))
        buf.write(bytes([len(email_bytes)]))
        buf.write(email_bytes)

    # Tag 4: Hardware ID (must be a multiple of 4 in length)
    if lic.hardware_id:
        if len(lic.hardware_id) % 4 != 0:
            raise ValueError("Invalid HWID (not multiple of 4): " + str(len(lic.hardware_id)))
        buf.write(bytes([4]))
        buf.write(bytes([len(lic.hardware_id)]))
        buf.write(lic.hardware_id)

    # Tag 5: Expiration Date (day, month, and two-byte year)
    if lic.expiration:
        day = lic.expiration.day
        month = lic.expiration.month
        year = lic.expiration.year
        buf.write(bytes([5]))
        buf.write(bytes([day]))
        buf.write(bytes([month]))
        buf.write(bytes([year % 256, year // 256]))

    # Tag 6: Running time limit
    if lic.running_time_limit and lic.running_time_limit > 0:
        if lic.running_time_limit > 255:
            raise ValueError("Running time limit is incorrect: " + str(lic.running_time_limit))
        buf.write(bytes([6]))
        buf.write(bytes([lic.running_time_limit]))

    # Tag 7: Product Code (expected as a Base64 string representing exactly 8 bytes)
    if lic.product_code:
        try:
            pc = base64.b64decode(lic.product_code)
        except Exception as e:
            raise ValueError(str(e))
        if len(pc) != 8:
            raise ValueError("Product code has invalid size: " + str(len(pc)))
        buf.write(bytes([7]))
        buf.write(pc)

    # Tag 8: User data
    if lic.user_data:
        if len(lic.user_data) > 255:
            raise ValueError("User data is too long: " + str(len(lic.user_data)))
        buf.write(bytes([8]))
        buf.write(bytes([len(lic.user_data)]))
        buf.write(lic.user_data)

    # Tag 9: Max build date
    if lic.max_build:
        day = lic.max_build.day
        month = lic.max_build.month
        year = lic.max_build.year
        buf.write(bytes([9]))
        buf.write(bytes([day]))
        buf.write(bytes([month]))
        buf.write(bytes([year % 256, year // 256]))

    result = buf.getvalue()
    if len(result) == 0:
        raise ValueError("Pack serial failed.")
    return result


def unpackSerial(data: bytes) -> "License":
    """
    Unpacks the binary blob (after RSA decryption) into a License instance.
    Verifies a 4-byte checksum (based on SHA-1) that was appended.
    """
    lic = License()
    i = 1
    # Skip padding: look for the first 0 byte
    while i < len(data) and data[i] != 0:
        i += 1
    if i == len(data):
        raise ValueError("Serial number parsing error (len).")
    i += 1  # Skip the 0 byte
    start = i
    end = None
    while i < len(data):
        tag = data[i]
        i += 1
        if tag == 1:
            lic.version = data[i]
            i += 1
        elif tag == 2:
            length = data[i]
            i += 1
            lic.name = data[i:i + length].decode('utf-8')
            i += length
        elif tag == 3:
            length = data[i]
            i += 1
            lic.email = data[i:i + length].decode('utf-8')
            i += length
        elif tag == 4:
            length = data[i]
            i += 1
            lic.hardware_id = data[i:i + length]
            i += length
        elif tag == 5:
            if i + 3 >= len(data):
                raise ValueError("Not enough data for expiration date")
            day = data[i]
            month = data[i + 1]
            year = data[i + 2] + data[i + 3] * 256
            lic.expiration = datetime(year, month, day)
            i += 4
        elif tag == 6:
            lic.running_time_limit = data[i]
            i += 1
        elif tag == 7:
            if i + 8 > len(data):
                raise ValueError("Not enough data for product code")
            pc = data[i:i + 8]
            lic.product_code = base64.b64encode(pc).decode('ascii')
            i += 8
        elif tag == 8:
            length = data[i]
            i += 1
            lic.user_data = data[i:i + length]
            i += length
        elif tag == 9:
            if i + 3 >= len(data):
                raise ValueError("Not enough data for max build date")
            day = data[i]
            month = data[i + 1]
            year = data[i + 2] + data[i + 3] * 256
            lic.max_build = datetime(year, month, day)
            i += 4
        elif tag == 255:
            end = i - 1
            break
        else:
            raise ValueError("Serial number parsing error (chunk).")
    if end is None or len(data) - end < 4:
        raise ValueError("Serial number CRC error.")
    sha1_hash = hashlib.sha1(data[start:end]).digest()
    rev_hash = sha1_hash[:4][::-1]
    given_hash = data[end + 1:end + 1 + 4]
    if rev_hash != given_hash:
        raise ValueError("Serial number CRC error.")
    return lic


def ParseLicense(serial: str, public: str, modulus: str, product_code: str, bits: int) -> "License":
    """
    Verifies the provided license key:
      - Filters and Base64-decodes the input.
      - Uses RSA public key data to "decrypt" the key.
      - Unpacks and validates the license data (including checksum and product code).
    """
    bytes_len = bits // 8
    try:
        tmp_serial = base64.b64decode(filterSerial(serial))
    except Exception:
        raise ValueError("Invalid serial number encoding.")

    if not (bytes_len - 6 <= len(tmp_serial) <= bytes_len + 6):
        raise ValueError("Invalid length.")

    decoded = decodeSerial(tmp_serial, public, modulus, bytes_len)
    lic = unpackSerial(decoded)
    if lic.version is None or not lic.product_code:
        raise ValueError("Incomplete serial number.")
    if lic.version != 1:
        raise ValueError("Unsupported version.")
    if lic.product_code != product_code:
        raise ValueError("Invalid product code.")
    return lic


SupportBits = [128, 256, 512, 1024, 2048, 4096]


# --- Configuration and License Classes ---

class Config:
    """
    Holds configuration parameters for license generation (and RSA signing).
    """

    def __init__(self, algorithm: str, bits: int, private: str, modules: str, product_code: str):
        if not algorithm or bits not in SupportBits or not private or not modules or not product_code:
            raise ValueError("Invalid configuration")
        self.algorithm = algorithm
        self.bits = bits
        self.private = private
        self.modules = modules
        self.product_code = product_code


def NewConfig(algorithm: str, bits: int, private: str, modules: str, product_code: str) -> Config:
    return Config(algorithm, bits, private, modules, product_code)


class License:
    """
    Represents a license with fields for user data, expiration, etc.
    """

    def __init__(self, name: str = "", email: str = "", expiration: datetime = None, max_build: datetime = None,
                 hardware_id: bytes = None, running_time_limit: int = 0, user_data: bytes = None,
                 product_code: str = "", version: int = 0):
        self.name = name
        self.email = email
        self.expiration = expiration
        self.max_build = max_build
        self.hardware_id = hardware_id
        self.running_time_limit = running_time_limit
        self.user_data = user_data
        self.product_code = product_code
        self.version = version

    def generate(self, config: Config) -> str:
        """
        Generates a license key:
          1. Packs license data.
          2. Appends a SHA‑1–derived 4-byte checksum (after marker 255).
          3. Adds custom random padding so that the overall size equals the RSA modulus size.
          4. Uses RSA (via modular exponentiation with the private key) to sign the data.
          5. Returns the key as a Base64-encoded string.
        """
        # Set the product code from configuration.
        self.product_code = config.product_code
        serial = packSerial(self)
        # Compute SHA‑1 hash and append marker (255) plus the reversed first 4 bytes.
        sha1_hash = hashlib.sha1(serial).digest()
        serial += bytes([255])
        serial += sha1_hash[:4][::-1]
        # Create front padding: 0x00 0x02, then random nonzero bytes, then 0x00.
        padding_front = bytearray([0, 2])
        pad_size = random.randint(8, 15)
        for _ in range(pad_size):
            padding_front.append(random.randint(1, 254))
        padding_front.append(0)
        content_size = len(serial) + len(padding_front)
        total_length = config.bits // 8
        rest = total_length - content_size
        if rest < 0:
            raise ValueError(
                "Content is too big to fit in key: {} bytes, maximal allowed is {} bytes".format(content_size,
                                                                                                 total_length))
        padding_back = bytearray()
        for _ in range(rest):
            padding_back.append(random.randint(0, 254))
        final_serial = bytes(padding_front) + serial + bytes(padding_back)
        # RSA "signing" (private key operation)
        raw_modules = base64.b64decode(config.modules)
        n_str = base10Encode(raw_modules)
        raw_private = base64.b64decode(config.private)
        d_str = base10Encode(raw_private)
        final_serial_str = base10Encode(final_serial)
        res_int = powmod(final_serial_str, d_str, n_str)
        result_bytes = base10Decode(res_int)
        # Ensure the result is exactly total_length bytes (pad with leading zeros if necessary)
        if len(result_bytes) < total_length:
            result_bytes = (b'\x00' * (total_length - len(result_bytes))) + result_bytes
        result_b64 = base64.b64encode(result_bytes).decode('ascii')
        return result_b64


# --- Example Usage ---

if __name__ == '__main__':
    # Generate a valid 1024-bit RSA key pair using PyCryptodome.
    key = RSA.generate(1024)
    modulus_bytes = key.n.to_bytes(128, byteorder='big')
    private_bytes = key.d.to_bytes(128, byteorder='big')
    public_bytes = key.e.to_bytes((key.e.bit_length() + 7) // 8, byteorder='big')

    # Base64-encode the RSA key components.
    example_private = base64.b64encode(private_bytes).decode('ascii')
    example_modules = base64.b64encode(modulus_bytes).decode('ascii')
    example_public = base64.b64encode(public_bytes).decode('ascii')
    # The product code must be 8 bytes (encoded in Base64).
    example_product_code = base64.b64encode(b'ABCDEFGH').decode('ascii')

    # Create the configuration using a 1024-bit key.
    config = NewConfig("RSA", 1024, example_private, example_modules, example_product_code)

    # Create a license with sample data.
    lic = License(
        name="John Doe",
        email="john@example.com",
        expiration=datetime(2025, 12, 31),
        hardware_id=b'\x01\x02\x03\x04',  # Must be a multiple of 4 in length.
        running_time_limit=60,
        user_data=b'custom data'
    )

    key_str = None
    try:
        key_str = lic.generate(config)
        print("Generated License Key:")
        print(key_str)
    except Exception as e:
        print("Error generating license:", e)

    # Now verify the license key (e.g., in your client application).
    if key_str:
        try:
            verified_license = ParseLicense(key_str, example_public, example_modules, example_product_code, config.bits)
            print("\nVerified License:")
            print("Name:", verified_license.name)
            print("Email:", verified_license.email)
            print("Expiration:", verified_license.expiration)
        except Exception as e:
            print("Error verifying license:", e)
