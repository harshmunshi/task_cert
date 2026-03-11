import json

def save_complete_text(data):
    overall_text = ""
    for paragraph in data["paragraphLinks"]:
        overall_text += paragraph["text"] + "\n"

    with open("complete_text_data.txt", "w") as f:
        f.write(overall_text)

if __name__ == "__main__":
    data = json.load(open("data/test_data.json", "r"))
    save_complete_text(data)