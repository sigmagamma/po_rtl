from src.file_tools import FileTools
def install_stanley(filename,language,store):
    answer = input("This is an alpha version. By proceeding you acknowledge you are responsible for running this. Press m or f to install male or female version, u to uninstall, any other key to quit")
    try:
        if answer in ['m','f','u']:
            print('Please select folder. This may appear in a separate window.')
        if answer in ['m','f']:
            ft = FileTools(filename, language,answer,store)
            ft.write_files()
        elif answer == 'u':
            ft = FileTools(filename,language,store)
            ft.remove_mod()
    except Exception as e:
        input("installer crashed with an error:\n"+str(e))
        exit()
    if answer in ['m','f','u']:
        input("Done, press any key to quit.")

