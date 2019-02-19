# $Id: html_groomer_plugin.py 222 2017-12-05 14:52:21Z jmcfarren $

import sublime
import sublime_plugin
from .html_groomer import HtmlGroomer


class HtmlGroomerCommand(sublime_plugin.TextCommand):


    def run(self, edit, actions=[], groomer_type='html'):
        groomer_settings = sublime.load_settings('HtmlGroomer.sublime-settings')
        groomer_settings.set('groomer_type', groomer_type)
        user_settings = sublime.load_settings("Preferences.sublime-settings")
        region = sublime.Region(0, self.view.size())
        groomer = HtmlGroomer(settings=groomer_settings, raw_content=self.view.substr(region))
        # if groomer.parser.stack.convert_indent:
        #     user_tab_size = user_settings.get('tab_size')
        #     if user_tab_size:
        #         tab_size = user_tab_size
        #     else:
        #         tab_size = groomer_settings.get('tab_size')
        #     self.view.settings().set('tab_size', groomer.parser.stack.native_tab_size)
        #     self.view.run_command('unexpand_tabs')
        #     self.view.settings().set('translate_tabs_to_spaces', False)
        #     self.view.settings().set('tab_size', tab_size)
        self.view.replace(edit, region, groomer.getGroomed())