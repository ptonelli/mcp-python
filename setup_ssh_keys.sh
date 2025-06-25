#!/bin/bash

# Define SSH directory
SSH_DIR="$HOME/.ssh"

# Check if directory exists before creating it
if [ ! -d "$SSH_DIR" ]; then
    mkdir -p "$SSH_DIR"
fi

# Always set permissions
chmod 700 "$SSH_DIR"

# Function to process each key type
setup_key() {
    local key_var="$1"
    local key_file="$2"
    local key_type="$3"
    
    # Check if variable is defined and not empty
    if [ -n "${!key_var}" ]; then
        echo "Found $key_type variable"
        
        # Check if file doesn't exist
        if [ ! -f "$SSH_DIR/$key_file" ]; then
            echo "Creating $key_type key file: $SSH_DIR/$key_file"
            
            # Decode base64 and write to file
            echo "${!key_var}" | base64 -d > "$SSH_DIR/$key_file"
            
            # Set correct permissions
            chmod 600 "$SSH_DIR/$key_file"
            echo "$key_type key file created successfully"
        else
            echo "$key_type key file already exists"
        fi
    else
        echo "$key_type variable not defined, skipping"
    fi
}

# Process each key type
setup_key "SSH_PRIVATE_KEY_RSA_B64" "id_rsa" "RSA"
setup_key "SSH_PRIVATE_KEY_ECDSA_B64" "id_ecdsa" "ECDSA"
setup_key "SSH_PRIVATE_KEY_ED25519_B64" "id_ed25519" "ED25519"

echo "SSH key setup completed"
