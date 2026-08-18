def get_config(url='https://6n37cqxfagcpkdulyw6ytfcmdu0jpouz.lambda-url.eu-central-1.on.aws/',
               key='MerlinV0gel'):

    import ast
    import time
    import requests
    import base64
    from pathlib import Path

    ##################
    # Get CPU Serial #
    ##################
    config = {}

    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    config[k.strip()] = v.strip()
    except Exception:
        config["Serial"] = "Unknown"


    ########
    # LOGO #
    ########
    if __name__ == "__main__":
        logo = open('merlin.txt').read()
    else:
        logo = open(Path('~/Projects/Portal/tools/').expanduser() / 'merlin.txt').read()
    print(f"{logo}\n{' ' + str(config['Serial']) + ' ':⣿^73}\n" + "⣿" * 73)



    ############################
    # Wait for internet access #
    ############################

    while True:
        try:
            requests.get('http://www.google.com', timeout=3)
            print("Internet connection established.")
            break
        except Exception:
            print("No internet connection. Retrying...")
            time.sleep(5)


    ##################
    # Request Lambda #
    ##################
    response = requests.get(url, params={"serial": config["Serial"]})
    response.raise_for_status()
    raw = response.content.strip()
    data = base64.b64decode(raw)

    ##################
    # XOR decrypt    #
    ##################
    key_bytes = key.encode()

    decrypted = bytes(
        data[i] ^ key_bytes[i % len(key_bytes)]
        for i in range(len(data))
    )

    dict_data = ast.literal_eval(decrypted.decode("utf-8"))

    return config | dict_data


if __name__ == "__main__":
    config = get_config()
    print(config)