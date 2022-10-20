def colorize(text:str,color:str):
    color_str = ""
    if color == "red":
        color_str = "\033[31m"
    elif color == "green":
        color_str = "\033[32m"
    elif color == "yellow":
        color_str = "\033[33m"
    elif color == "blue":
        color_str = "\033[34m"
    elif color == "purple":
        color_str = "\033[35m"
    elif color == "cyan":
        color_str = "\033[36m"
    return color_str+text+"\033[0m"

def rprint(text:str,end:str="\n> "):
    print("\r"+text,end=end)

def rcprint(text:str,color:str,end:str="\n> "):
    rprint(colorize(text,color),end)

def format_messge(received:bool,user:str,msg:str):
    if received:
        return f"<{user}|: {msg}"
    else:
        return f"|{user}>: {msg}"