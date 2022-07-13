import os
import sys
import winreg
from shutil import copyfile,copy,rmtree
from os import path
from distutils.dir_util import copy_tree
import vpk

import src.text_tools as tt
import subprocess
import json
import shlex
import re
from urllib.request import urlopen

REPO = "https://github.com/sigmagamma/portl/"
# this is required due to AV software flagging shutil.move for some reason
def move(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    copyfile(src,dst)
    os.remove(src)
class FileTools:
    def __init__(self, game_filename,language):

        if (game_filename is not None):
            with open(self.get_patch_gamedata(game_filename),'r') as game_data_file:
                data = json.load(game_data_file)
                if data is not None:
                    # text and filenames logic
                    self.game = data['game']
                    game_service = data.get('game_service')
                    self.os = data.get('os')
                    if game_service is not None and self.os is not None:
                        if game_service != 'Steam':
                            raise Exception(
                                "currently only Steam is supported")
                        else:
                            if self.os == 'WIN':
                                self.game_parent_path = self.steam_path_windows()
                            else:
                                raise Exception(
                                    "currently only Windows is supported")
                    else:
                        self.game_parent_path = self.steam_path_windows()
                    self.shortname = data['shortname']
                    self.version = data['version']
                    self.basegame = data['basegame']
                    self.basegame_path = "\\" + self.game + "\\" + self.basegame
                    full_basegame_path = self.get_full_basegame_path()
                    if not os.path.exists(full_basegame_path):
                        raise Exception("folder "+full_basegame_path + " doesn't exist. Please install the game. ")
                    self.original_language = self.get_original_localization_lang()
                    self.language = language

                    self.caption_file_name = data['caption_file_name']
                    self.other_files = data.get('other_files')
                    if self.other_files is None:
                        self.other_files = []
                    self.max_chars_before_break = data['max_chars_before_break']
                    self.total_chars_in_line = data.get('total_chars_in_line')
                    compiler_game_service_path = data.get('compiler_game_service_path')
                    if compiler_game_service_path is not None:
                        self.compiler_game_parent_path = compiler_game_service_path
                        self.compiler_basegame_path = data.get('compiler_game_path')
                        self.compiler_game = data.get('compiler_game')
                    else:
                        self.compiler_game_parent_path = self.game_parent_path
                        self.compiler_basegame_path = self.basegame_path
                        self.compiler_game = self.game
                    self.compiler_path = self.get_compiler_path()
                    self.english_captions_text_path = data.get('english_captions_text_path')
                    if self.english_captions_text_path is None:
                        self.english_captions_text_path = self.get_english_captions_text_path()
                    else:
                        self.english_captions_text_path = self.get_patch_file_path(self.english_captions_text_path)

                    # mod folder logic
                    mod_type = data.get('mod_type')
                    self.mod_type = mod_type
                    if mod_type == 'custom':
                        self.mod_folder = self.get_custom_folder()
                    elif mod_type == 'dlc':
                        self.mod_folder = self.get_dlc_folder()
                    self.vpk_file_name = data.get("vpk_file_name")
                    private_file = self.get_patch_gamedata_private(game_filename)
                    self.captions_translation_url = None
                    self.translation_url = None
                    if os.path.exists(private_file):
                        with  open(private_file,'r') as game_data_file_private:
                            data_private = json.load(game_data_file_private)
                            self.translation_url = data_private.get('translation_url')
                            translation_sheet = data.get('captions_translation_sheet')
                            if self.translation_url is not None and translation_sheet is not None:
                                self.captions_translation_url = self.translation_url + translation_sheet

    ##Steam/Epic logic
    def steam_path_windows(self):
        try:
            hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\WOW6432Node\Valve\Steam")
        except:
            hkey = None
            print(sys.exc_info())
        try:
            steam_path = winreg.QueryValueEx(hkey, "InstallPath")
        except:
            steam_path = None
            print(sys.exc_info())
        return steam_path[0] + "\steamapps\common"

    def steam_path_linux(self):
        return "~/.steam/steam/steamapps/common"

    def steam_path_macos(self):
        return "~/Library/Application Support/Steam/SteamApps/common"
    ## general folder logic
    # patch are the local files of the patch.
    # basegame is the content folder for the original game (usually something like portal/portal)
    # mod is where the mod gets placed (for instance portal/custom/portl)
    # compiler is where caption compilation happens

    def get_patch_gamedata(self,game_filename):
        filename = game_filename
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            filename = path.abspath(path.join(path.dirname(__file__), filename))
        return filename
    def get_patch_gamedata_private(self,game_filename):
        filename = game_filename.replace(".json"," private.json")
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            filename = path.abspath(path.join(path.dirname(__file__), filename))
        return filename
    def get_full_game_path(self):
        return self.game_parent_path + "\\"+self.game

    def get_full_basegame_path(self):
        return self.game_parent_path + self.basegame_path

    def get_basegame_cache_folder(self):
        return self.get_full_basegame_path() + "\\maps\\soundcache"

    def get_basegame_cache_path(self):
        return self.get_basegame_cache_folder()+"\_master.cache"

    def get_basegame_resource_folder(self):
        return self.get_full_basegame_path() + "\\resource"

    def get_basegame_subfolder(self,subfolder):
        return self.get_full_basegame_path() + "\\"+subfolder

    def search_dlc_folders(self):
        dlcs = [a for a in os.listdir(self.get_full_game_path()) if a.startswith(self.basegame+'_dlc')]
        dlc_seq = 0
        for dlc in dlcs:
            number = dlc.replace(self.basegame+'_dlc','')
            if number.isnumeric():
                num = int(number)
                if num > dlc_seq:
                    dlc_seq = num
            folder = self.get_full_game_path()+"\\"+dlc
            if os.path.exists(folder + "\\" + "portl.txt"):
                return folder,dlc_seq
        return None,dlc_seq
    def get_dlc_folder(self):
        folder,number = self.search_dlc_folders()
        if folder is not None:
            return folder
        number = number + 1
        return self.get_full_basegame_path() + "_dlc" + str(number)

    def get_custom_parent_folder(self):
        return self.get_full_basegame_path() + "\custom"

    def get_custom_folder(self):
        return self.get_custom_parent_folder()+"\portl"

    def get_sizepatch_custom_folder(self):
        return self.get_custom_parent_folder()+"\sizepatch"

    def get_mod_resource_folder(self):
        return self.mod_folder+"\\resource"

    def get_mod_subfolder(self,subfolder):
        return self.mod_folder + "\\"+subfolder

    def get_mod_scripts_folder(self):
        return self.mod_folder+"\\scripts"


    def get_mod_cache_folder(self):
        return self.mod_folder+"\\maps\\soundcache"

    def get_patch_version_file(self):
        filename = self.get_gamefiles_folder() + "\\portl.txt"
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            filename = path.abspath(path.join(path.dirname(__file__), filename))
        return filename
    def get_mod_version_path(self):
        return self.mod_folder + "\\portl.txt"
    def write_patch_version_file(self):
        rtl_text=""
        if self.total_chars_in_line is not None:
            rtl_text = "RTL version\n"
        with open(self.get_mod_version_path(),'w') as file:
            file.write(self.shortname+"-"+self.version+" "+rtl_text+"\n"+ REPO)
    def create_mod_folders(self):
        cfg_folder = self.get_mod_cfg_folder()
        if not os.path.exists(cfg_folder):
            os.makedirs(cfg_folder)
        # TODO make this game specific
        for folder in ['resource','scripts','resource\\ui\\basemodui']:
            mod_subfolder = self.get_mod_subfolder(folder)
            if not os.path.exists(mod_subfolder):
                os.makedirs(mod_subfolder)
        # see here: https://github.com/sigmagamma/portal-text-size-changer
        sizepatch_folder = self.get_sizepatch_custom_folder()
        if os.path.exists(sizepatch_folder):
            rmtree(sizepatch_folder)
        self.write_patch_version_file()
        if self.mod_type == 'dlc':
            basegame_cache_path = self.get_basegame_cache_path()
            if not os.path.exists(basegame_cache_path):
                input("Note: You'll have to start the game, get to the loading screen, wait for a while, and then restart it. Press any key.")
            else:
                mod_cache_folder = self.get_mod_cache_folder()
                if not os.path.exists(mod_cache_folder):
                    os.makedirs(mod_cache_folder)
                copy(basegame_cache_path,mod_cache_folder)
    def remove_mod_folder(self):
        if os.path.exists(self.mod_folder):
            rmtree(self.mod_folder)
    def remove_mod(self):
        self.remove_mod_folder()
        for file_data in self.other_files:
            if file_data.get('override'):
                self.restore_basegame_english_other_path(file_data)

    def get_compiler_resource_folder(self):
        return self.compiler_game_parent_path + self.compiler_basegame_path + "\\resource"

    def get_compiler_path(self):
        return self.compiler_game_parent_path + \
               "\{}\\bin\captioncompiler.exe".format(self.compiler_game)

    ## Close Captions logic

    def get_mod_captions_path(self):
        return self.get_mod_resource_folder() + "\{}_{}.dat".format(self.caption_file_name,self.original_language)

    def get_compiled_captions_path(self):
        return self.get_compiler_resource_folder()+"\{}_{}.dat".format(self.caption_file_name,self.language)

    def get_to_compile_text_path(self):
        return self.get_compiler_resource_folder()+"\{}_{}.txt".format(self.caption_file_name,self.language)


    def get_mod_captions_text_path(self):
        return self.get_mod_resource_folder() + "\{}_{}.txt".format(self.caption_file_name,self.original_language)

    def get_patch_captions_path(self):
        filename = self.get_gamefiles_folder() + "\\{}_{}.dat".format(self.caption_file_name, "english")
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            filename = path.abspath(path.join(path.dirname(__file__), filename))
        return filename


    def get_english_captions_text_path(self):
        return self.get_basegame_resource_folder()+"\{}_english.txt".format(self.caption_file_name)
    def get_gamefiles_folder(self):
        return "gamefiles\\"+self.shortname

    def get_patch_captions_csv_path(self):
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return self.game + " translation - " + self.caption_file_name + ".csv"
        else:
            return self.get_gamefiles_folder() + "\\" + self.game + " translation - " + self.caption_file_name + ".csv"

    def write_captions_from_patch(self):
        dest_captions_path = self.get_mod_captions_path()
        copyfile(self.get_patch_captions_path(), dest_captions_path)

    def write_captions_from_csv(self,csv_path):
        orig_captions_text_path = self.english_captions_text_path
        to_compile_text_path = self.get_to_compile_text_path()
        translated_path = "{}_{}.txt".format(self.caption_file_name,self.language)
        translated_lines = tt.read_translation_from_csv(csv_path)
        if not os.path.exists(orig_captions_text_path):
            raise Exception("file "+ orig_captions_text_path+ " doesn't exist. Verify game files integrity")
        tt.translate(orig_captions_text_path,translated_path,translated_lines,True,self.max_chars_before_break,self.total_chars_in_line,'utf-16',self.language)
        move(translated_path,to_compile_text_path)
        # this works because "translated path" is also the file name of to_compile_text_path
        subprocess.run([self.compiler_path,translated_path], cwd=self.get_compiler_resource_folder())
        compiled_captions_path = self.get_compiled_captions_path()
        dest_captions_path = self.get_mod_captions_path()
        move(compiled_captions_path,dest_captions_path)
        # Let's be nice and also move the uncompiled file to the mod folder
        dest_captions_text_path = self.get_mod_captions_text_path()
        move(to_compile_text_path,dest_captions_text_path)

    ## Other files logic - text files not for compilation
    def get_mod_other_path(self, file_data):
        override = file_data.get('override')
        if override:
            language = self.get_localized_suffix(file_data,"english")
        else:
            language = self.get_localized_suffix(file_data,self.original_language)
        name = file_data.get('name')
        extension = file_data.get('extension')
        folder = file_data.get('folder')
        return self.get_mod_subfolder(folder)+"\{}{}.{}".format(name,language,extension)
    def get_localized_suffix(self,file_data,language):
        localized = file_data.get('localized')
        if localized:
            return "_"+language
        return ""
    def get_basegame_english_path(self,file_data,backup_flag):
        folder = self.get_basegame_subfolder(file_data.get('folder'))
        language = self.get_localized_suffix(file_data,"english")
        backup = ""
        if backup_flag:
            backup = "_backup"
        path = folder +"\\"+file_data.get('name')+language+backup+"."+file_data.get('extension')
        return path

    def get_basegame_english_other_path(self,file_data):
        return self.get_basegame_english_path(file_data,backup_flag=False)
    def get_basegame_english_backup_other_path(self,file_data):
        return self.get_basegame_english_path(file_data,backup_flag=True)

    def backup_basegame_english_other_path(self,file_data):
        orig_path = self.get_basegame_english_other_path(file_data)
        if os.path.exists(orig_path):
            move(orig_path, self.get_basegame_english_backup_other_path(file_data))
    def restore_basegame_english_other_path(self, file_data):
        backup_path = self.get_basegame_english_backup_other_path(file_data)
        if os.path.exists(backup_path):
            move(backup_path,self.get_basegame_english_other_path(file_data))

    def get_local_other_path(self,file_data):
        language = self.get_localized_suffix(file_data,"english")
        return self.get_gamefiles_folder() + "\\"+file_data.get('name')+language+"."+file_data.get('extension')

    def get_patch_other_path(self,file_data):
        filename = self.get_local_other_path(file_data)
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            filename = path.abspath(path.join(path.dirname(__file__), filename))
        return filename

    def get_patch_other_csv_path(self,file_data):
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return self.game + " translation - " + file_data.get('name') + ".csv"
        else:
            return self.get_gamefiles_folder() + "\\" + self.game + " translation - " + file_data.get('name') + ".csv"

    def write_other_from_patch(self,file_data):
        dest_other_path = self.get_mod_other_path(file_data)
        copyfile(self.get_patch_other_path(file_data), dest_other_path)

    def write_other_from_csv(self,file_data,csv_path):
        dest_other_path = self.get_mod_other_path(file_data)
        is_on_vpk = file_data.get('is_on_vpk')
        folder = file_data.get('folder')
        name = file_data.get('name')
        extension = file_data.get('extension')
        multi_line = file_data.get('multi_line')
        compile = file_data.get('compile')
        language = self.get_localized_suffix(file_data,'english')
        if is_on_vpk:
            source_other_path = self.get_patch_other_path(file_data)
            self.save_file_from_vpk(folder+"/"+name+language+'.'+extension,source_other_path)
        else:
            basegame_other_path = self.get_basegame_english_other_path(file_data)

            backup_basegame_other_path = self.get_basegame_english_backup_other_path(file_data)
            if os.path.exists(basegame_other_path):
                source_other_path = basegame_other_path
            elif os.path.exists(backup_basegame_other_path):
                source_other_path = backup_basegame_other_path
            else:
                raise Exception(
                    "file " + basegame_other_path + " or " + backup_basegame_other_path + " don't exist. Verify game files integrity")
        translated_lines = tt.read_translation_from_csv(csv_path)
        encoding = file_data.get('encoding')
        # if compile:
        #     encoding = 'utf-16'
        # elif is_on_vpk:
        #     encoding = None
        # elif extension == 'res':
        #     encoding = 'utf-8'
        # else:
        #     encoding = 'utf-16'
        tt.translate(source_other_path,dest_other_path,translated_lines,multi_line,self.max_chars_before_break,self.total_chars_in_line,encoding,self.language)
        if compile:
            to_compile_text_path = self.get_to_compile_text_path()
            move(dest_other_path, to_compile_text_path)
            # this works because "translated path" is also the file name of to_compile_text_path
            subprocess.run([self.compiler_path, to_compile_text_path], cwd=self.get_compiler_resource_folder())
            #TODO generalize this
            compiled_captions_path = self.get_compiled_captions_path()
            dest_captions_path = self.get_mod_captions_path()
            move(compiled_captions_path, dest_captions_path)
            # Let's be nice and also move the uncompiled file to the mod folder
            dest_captions_text_path = self.get_mod_captions_text_path()
            move(to_compile_text_path, dest_captions_text_path)
        if is_on_vpk:
            os.remove(source_other_path)

    def get_basegame_vpk_path(self):
        return self.get_full_basegame_path() + "\\" + self.vpk_file_name

    def save_file_from_vpk(self,path_in_vpk,path_on_disk):
        vpk_path = self.get_basegame_vpk_path()
        if os.path.exists(vpk_path):
            pak = vpk.open(vpk_path)
            pakfile = pak.get_file(path_in_vpk)
            pakfile.save(path_on_disk)

        else:
            raise Exception("file " +vpk_path + " doesn't exist. Verify game files integrity")

    # assets logic - copy entire folders from patch
    def get_mod_asset_path(self,filename):
        return self.mod_folder+"/"+filename

    def get_patch_file_path(self, filename):
        filename = self.get_gamefiles_folder()+"\\"+filename
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            filename = path.abspath(path.join(path.dirname(__file__), filename))
        return filename

    def copy_assets(self):
        for filename in ["materials","sound"]:
            src_path = self.get_patch_file_path(filename)
            if os.path.exists(src_path):
                copy_tree(src_path,self.get_mod_asset_path(filename),preserve_mode=0)

    def get_mod_cfg_folder(self):
        return self.mod_folder + "\cfg"

    def get_mod_cfg_path(self, filename):
        return self.get_mod_cfg_folder() + "\{}".format(filename)

    def get_basegame_cfg_folder(self):
        return self.get_full_basegame_path() + "\cfg"
    def get_basegame_cfg_path(self, filename):
        return self.get_basegame_cfg_folder()+"\{}".format(filename)

    def get_lang_from_cfg(self,cfg_path):
        lang = ''
        if (os.path.isfile(cfg_path)):
            with open(cfg_path, 'r') as f_in:
                for line in f_in:
                    if lang == '' and line.startswith("cc_lang"):
                        lang_line = line
                        lang = (lang_line.split('"'))[1]
                        break
        return lang

    # best effort to find user's localization lang and override it so that after
    # uninstallation configuration won't be affected
    def get_original_localization_lang(self):
        src_config_path = self.get_basegame_cfg_path('config.cfg')
        lang = self.get_lang_from_cfg(src_config_path)
        # using a non-official localization as the language to override was a mistake
        # might not be able to correct it, but can avenge it
        if lang == '' or lang == 'hebrew':
            lang = 'english'
        return lang

    def write_autoexec_cfg(self):
        with open(self.get_mod_cfg_path('autoexec.cfg'), 'w') as file:
            file.write('cc_subtitles "1"\n')
            file.write('cc_lang "' + self.original_language + '"')

    def get_csv_from_url(self,filename,url):
        response = urlopen(url)
        if response.status == 200:
            with open(filename, 'w', encoding='utf-8') as file:
                for line in response:
                    file.write(line.decode('utf-8'))

    ## main write function
    def write_files(self):
        self.create_mod_folders()
        self.write_autoexec_cfg()
        captions_csv_path = self.get_patch_captions_csv_path()

        # if self.captions_translation_url is not None:
        #     self.get_csv_from_url(captions_csv_path,self.captions_translation_url)
        # if (os.path.isfile(captions_csv_path)):
        #     self.write_captions_from_csv(captions_csv_path)
        #     if self.captions_translation_url is not None:
        #         os.remove(captions_csv_path)
        #TODO handle patch end case for compilation

        # if not os.path.isfile(captions_csv_path):
        #    self.write_captions_from_patch()
        for file_data in self.other_files:
            other_csv_path = self.get_patch_other_csv_path(file_data)
            sheet = file_data.get("translation_sheet")

            if sheet is not None and self.translation_url is not None:
                file_url = self.translation_url + sheet
                self.get_csv_from_url(other_csv_path, file_url)
            if os.path.isfile(other_csv_path):
                self.write_other_from_csv(file_data,other_csv_path)
                if file_url is not None:
                    os.remove(other_csv_path)
            else:
                self.write_other_from_patch(file_data)
            if file_data.get('override'):
                self.backup_basegame_english_other_path(file_data)
        self.copy_assets()