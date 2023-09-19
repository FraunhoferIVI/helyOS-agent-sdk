

def replicate_helyos_client(helyos_client):
    """Create a new helyos client object using the same initialization parameters as the original one."""

    return helyos_client.__class__(helyos_client.rabbitmq_host,
                        helyos_client.rabbitmq_port,
                        helyos_client.uuid,helyos_client.enable_ssl,
                        helyos_client.ca_certificate, helyos_client.helyos_public_key,
                        helyos_client.private_key, helyos_client.public_key)