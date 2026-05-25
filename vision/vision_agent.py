from ollama import chat

def analyze_image(image_path):

    response = chat(
        model="qwen2.5vl",

        messages=[
            {
                "role": "user",
                "content": "Describe this image",
                "images": [image_path]
            }
        ]
    )

    return response
