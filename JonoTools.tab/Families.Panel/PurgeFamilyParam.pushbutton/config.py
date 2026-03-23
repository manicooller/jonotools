# -*- coding: utf-8 -*-
"""Configuration for Purge Shared Params (Shift+Click)"""

from pyrevit import script, forms

cfg = script.get_config()

# Default examples formatted as actual Shared Parameter file lines (using fake GUIDs)
DEFAULT_TEXT = (
    "PARAM\t11111111-2222-3333-4444-555555555555\tJONO_Default Width\tLENGTH\t\t1\t1\t\t1\t0\n"
    "PARAM\taaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\tJONO_Default Height\tLENGTH\t\t1\t1\t\t1\t0\n"
    "PARAM\t99999999-8888-7777-6666-555555555555\tJONO_Default Depth\tLENGTH\t\t1\t1\t\t1\t0"
)

# Fetch currently saved text or use defaults
current_text = getattr(cfg, 'purge_whitelist_raw', DEFAULT_TEXT)

# Define the WPF UI
xaml_layout = """
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Purge Whitelist Settings" Height="450" Width="800" 
        WindowStartupLocation="CenterScreen" ShowInTaskbar="False">
    <Grid Margin="10">
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>
        
        <TextBlock Text="Paste your Shared Parameters file contents here:" 
                   Grid.Row="0" Margin="0,0,0,2" FontWeight="Bold"/>
        <TextBlock Text="Note: You can paste the entire file. Headers, groups, and empty lines will be automatically ignored." 
                   Grid.Row="1" Margin="0,0,0,10" FontStyle="Italic" Foreground="Gray"/>
                   
        <TextBox x:Name="params_tb" Grid.Row="2" 
                 AcceptsReturn="True" AcceptsTab="True"
                 TextWrapping="NoWrap" 
                 HorizontalScrollBarVisibility="Auto"
                 VerticalScrollBarVisibility="Auto" 
                 FontFamily="Consolas" FontSize="11"/>
                 
        <StackPanel Grid.Row="3" Orientation="Horizontal" HorizontalAlignment="Right" Margin="0,10,0,0">
            <Button x:Name="reset_btn" Content="Reset to Default" Width="120" Height="30" Margin="0,0,10,0" Click="reset_clicked"/>
            <Button x:Name="save_btn" Content="Save &amp; Filter" Width="120" Height="30" FontWeight="Bold" Click="save_clicked"/>
        </StackPanel>
    </Grid>
</Window>
"""

class SettingsDialog(forms.WPFWindow):
    def __init__(self, initial_text):
        forms.WPFWindow.__init__(self, xaml_layout, literal_string=True)
        self.params_tb.Text = initial_text

    def save_clicked(self, sender, args):
        raw_lines = self.params_tb.Text.replace("\r", "").split("\n")
        valid_lines = []
        
        # Parse looking for valid tab-separated PARAM lines
        for line in raw_lines:
            parts = line.split('\t')
            if len(parts) >= 3 and parts[0] == 'PARAM':
                valid_lines.append(line.strip())
        
        # Save only the clean, valid lines
        cfg.purge_whitelist_raw = "\n".join(valid_lines)
        script.save_config()
        
        forms.alert("Settings Saved!\n\nExtracted {} valid parameter(s) to keep.".format(len(valid_lines)), title="Success")
        self.Close()

    def reset_clicked(self, sender, args):
        self.params_tb.Text = DEFAULT_TEXT

# Show the dialog
dialog = SettingsDialog(current_text)
dialog.show_dialog()
