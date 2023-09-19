from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends.openssl.rsa import _RSAPrivateKey
import json


def generate_private_public_keys():
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    priv = key.private_bytes(encoding=serialization.Encoding.PEM,
                             format=serialization.PrivateFormat.TraditionalOpenSSL, encryption_algorithm=serialization.NoEncryption())
    pub_key = key.public_key()
    pub = pub_key.public_bytes(encoding=serialization.Encoding.PEM,
                               format=serialization.PublicFormat.SubjectPublicKeyInfo)
    return priv, pub


def verify_signature(message_string, signature, public_key):
    """ Verify the signature of a message with the public key provided

        Implements the function that verifies the signature of a message

        :param message_string: The message
        :type message_string: str
        :param signature: The signature of the message in hex or bytes format
        :type signature: bytes, str
        :param public_key: The public key for verifying the signature of the message
        :type public_key: bytes, str, list

    """
    try:
        # Load the public key from PEM format
        if type(public_key) is bytes:
            pubkey = serialization.load_pem_public_key(
                public_key, backend=default_backend())
        elif type(public_key) is str:
            pubkey = serialization.load_pem_public_key(
                public_key.encode('utf-8'), backend=default_backend())
        elif type(public_key) is list:
                pubkey_bytes = bytes(public_key)
                pubkey = serialization.load_pem_public_key(
                pubkey_bytes, backend=default_backend())
        else:
            raise TypeError(f'Public key type not supported, type: {type(public_key)}, contents: {public_key}')
    except Exception as e:
        raise Exception(
            f'Error loading public key for signature verification: {e}')
    try:
        # Verify the signature
        # Padding: PSS is the recommended choice for any new protocols or applications, PKCS1v15 should only be used to support legacy protocols.
        # verify signature using hex string signature
        
        if type(signature) is str:
            byte_signature = bytes.fromhex(signature)
        else:
            byte_signature = signature

        pubkey.verify(
            byte_signature,
            message_string.encode('utf-8'),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256()
        )
        return True

    except Exception as e:
        raise Exception(f'Error verifying signature: {e}. Signature: {signature}, message: {message_string}')


class Signing:
    def __init__(self, private_key=None) -> None:
        """ Signing class

            Implements several functions to facilitate the handling of private keys and the signing of messages.

            :param private_key: The private key for signing the messages
            :type private_key: bytes, str, _RSAPrivateKey

        """

        if type(private_key) is bytes:
            self.private_key_string = private_key.decode('utf-8')
            try:
                # Load the key from PEM format
                self.private_key = serialization.load_pem_private_key(
                    data=private_key,
                    password=None,
                    backend=default_backend()
                )
            except Exception as e:
                raise Exception(f'Error loading private key: {e}')

        if type(private_key) is str:
            self.private_key_string = private_key
            try:
                # Load the key from PEM format
                self.private_key = serialization.load_pem_private_key(
                    data=private_key.encode('utf-8'),
                    password=None,
                    backend=default_backend()
                )
            except Exception as e:
                raise Exception(f'Error loading private key: {e}')

        if type(private_key) is _RSAPrivateKey:
            self.private_key = private_key
            private_key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            self.private_key_string = private_key_pem.decode('utf-8')

        if private_key is not None:
            self.own_public_key = self.private_key.public_key()
            self.own_public_key_pem = self.own_public_key.public_bytes(encoding=serialization.Encoding.PEM,
                                                                       format=serialization.PublicFormat.SubjectPublicKeyInfo)

    def verify_own_signature(self, message_string, signature):
        """ Verify the signature of a message signed with the private key provided

            Verification only
            Implements the function that verifies the signature of a message signed with the own private key

            :param message_string: The message
            :type message_string: str
            :param signature: The signature of the message
            :type signature: bytes, str

        """
        try:
            # Verify the signature
            # Padding: PSS is the recommended choice for any new protocols or applications, PKCS1v15 should only be used to support legacy protocols.
            self.own_public_key.verify(
                signature,
                message_string.encode('utf-8'),
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                            salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256()
            )
            return True

        except Exception as e:
            raise Exception(f'Error verifying signature: {e}')


    def return_signature(self, message_string):
        """ Signs the message string provided and returns signature in bytes format
            :param message_string: The message str
            :type message_string: str

        """
        try:
            signature = self.private_key.sign(
                message_string.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256()
            )
        except Exception as e:
            raise Exception(f'Error signing message: {e}')

        return signature
