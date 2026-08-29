using Kingmaker.UI.Models.SettingsUI;
using Kingmaker.UI.Models.SettingsUI.SettingAssets;
using NeuralSpeechMod.Localization;
using UnityEngine;

namespace NeuralSpeechMod.Configuration.UI;

public static class OwlcatUITools
{
    public static UISettingsGroup MakeSettingsGroup(string key, string name, params UISettingsEntityBase[] settings)
    {
        var group = ScriptableObject.CreateInstance<UISettingsGroup>();
        group.name = key;
        group.Title = ModLocalizationManager.CreateString(key, name);

        group.SettingsList = settings;

        return group;
    }
}
