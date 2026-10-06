using System;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using UnityEngine.Audio;

namespace MultiBash.EditorTools
{
    public static partial class MultiBashSetup
    {
        public const string MixerPath = AudioDir + "/MultiBashMixer.mixer";

        /// <summary>Exposed volume parameters on the mixer (decibels). AudioManager drives them from the volume sliders.</summary>
        public static readonly string[] MixerGroups = { "Music", "SFX", "UI" };

        /// <summary>
        /// Creates Audio/MultiBashMixer.mixer: Master > Music / SFX / UI, each group's volume exposed as
        /// "MusicVolume" / "SFXVolume" / "UIVolume". Unity has no public API for building mixers, so this uses the
        /// editor's own (internal) mixer controller. Existing mixers are left alone (open it to tweak by hand).
        /// </summary>
        [MenuItem("MultiBash/Setup/Create Audio Mixer", priority = 5)]
        public static AudioMixer BuildMixer()
        {
            var existing = AssetDatabase.LoadAssetAtPath<AudioMixer>(MixerPath);
            if (existing != null) return existing;
            var asm = typeof(Editor).Assembly;
            var ctrlType = asm.GetType("UnityEditor.Audio.AudioMixerController");
            const BindingFlags all = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance;
            var ctrl = ctrlType.GetMethod("CreateMixerControllerAtPath", all).Invoke(null, new object[] { MixerPath });
            var master = ctrlType.GetProperty("masterGroup", all).GetValue(ctrl);
            var pathType = asm.GetType("UnityEditor.Audio.AudioGroupParameterPath");
            var exposedField = ctrlType.GetProperty("exposedParameters", all);
            foreach (var name in MixerGroups)
            {
                var g = ctrlType.GetMethod("CreateNewGroup", all).Invoke(ctrl, new object[] { name, false });
                ctrlType.GetMethod("AddChildToParent", all).Invoke(ctrl, new[] { g, master });
                var guid = g.GetType().GetMethod("GetGUIDForVolume", all).Invoke(g, null);
                var path = Activator.CreateInstance(pathType, g, guid);
                ctrlType.GetMethod("AddExposedParameter", all).Invoke(ctrl, new[] { path });
                // the new exposed parameter is called "MyExposedParam..."; rename it
                var arr = (Array)exposedField.GetValue(ctrl);
                for (int i = 0; i < arr.Length; i++)
                {
                    var p = arr.GetValue(i);
                    var gf = p.GetType().GetField("guid", all);
                    if (!gf.GetValue(p).Equals(guid)) continue;
                    p.GetType().GetField("name", all).SetValue(p, name + "Volume");
                    arr.SetValue(p, i);
                }
                exposedField.SetValue(ctrl, arr);
            }
            EditorUtility.SetDirty((UnityEngine.Object)ctrl);
            AssetDatabase.SaveAssets();
            var mixer = AssetDatabase.LoadAssetAtPath<AudioMixer>(MixerPath);
            Debug.Log($"[MultiBash] Created {MixerPath} with groups {string.Join(", ", MixerGroups)}.");
            return mixer;
        }

        static AudioMixerGroup MixerGroup(AudioMixer mixer, string name) =>
            mixer == null ? null : mixer.FindMatchingGroups(name).FirstOrDefault(g => g.name == name);
    }
}
