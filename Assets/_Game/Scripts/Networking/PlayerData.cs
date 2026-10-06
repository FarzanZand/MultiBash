using System.Collections.Generic;
using Fusion;
using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// One per connected player. Survives scene changes (Lobby -> Game -> Lobby).
    /// Holds lobby choices (name, character, ready) and run stats (kills, damage).
    /// </summary>
    public class PlayerData : NetworkBehaviour
    {
        public static readonly List<PlayerData> All = new();

        [Networked] public NetworkString<_16> Nickname { get; set; }
        [Networked] public int CharacterIndex { get; set; }
        [Networked] public NetworkBool Ready { get; set; }
        [Networked] public int Kills { get; set; }
        [Networked] public float DamageDealt { get; set; }
        [Networked] public int JoinOrder { get; set; }

        /// <summary>The in-game character (only set in the Game scene).</summary>
        public PlayerCharacter Character { get; set; }

        public PlayerRef Player => Object.InputAuthority;
        public bool IsLocal => Object != null && Object.HasInputAuthority;
        [Networked] public NetworkBool IsHost { get; set; }
        /// <summary>Only meaningful on the host's PlayerData: the map the party will play.</summary>
        [Networked] public int MapIndex { get; set; }

        public static PlayerData Host
        {
            get
            {
                foreach (var p in All) if (p != null && p.Object != null && p.Object.IsValid && p.IsHost) return p;
                return null;
            }
        }

        static int _joinCounter;

        public static PlayerData Local
        {
            get
            {
                foreach (var p in All) if (p != null && p.IsLocal) return p;
                return null;
            }
        }

        public static PlayerData Get(PlayerRef player)
        {
            foreach (var p in All) if (p != null && p.Object != null && p.Object.InputAuthority == player) return p;
            return null;
        }

        public override void Spawned()
        {
            Runner.MakeDontDestroyOnLoad(gameObject);
            if (!All.Contains(this)) All.Add(this);
            All.Sort((a, b) => a.JoinOrder.CompareTo(b.JoinOrder));

            if (HasStateAuthority)
            {
                JoinOrder = ++_joinCounter;
                Nickname = "Player";
                IsHost = Object.InputAuthority == Runner.LocalPlayer;
                if (IsHost) MapIndex = Mathf.Clamp(PlayerPrefs.GetInt("map", 0), 0, Mathf.Max(0, GameDatabase.Instance.maps.Count - 1));
            }

            if (HasInputAuthority)
            {
                int savedChar = PlayerPrefs.GetInt("character", 0);
                Rpc_SetInfo(GameLauncher.PlayerName, savedChar);
            }
        }

        public override void Despawned(NetworkRunner runner, bool hasState)
        {
            All.Remove(this);
        }

        public string DisplayName => string.IsNullOrEmpty(Nickname.Value) ? "Player" : Nickname.Value;

        // ------------------------------------------------------------------ RPCs (client -> host)

        [Rpc(RpcSources.InputAuthority, RpcTargets.StateAuthority)]
        public void Rpc_SetInfo(string nickname, int characterIndex)
        {
            nickname = string.IsNullOrWhiteSpace(nickname) ? "Player" : nickname.Trim();
            if (nickname.Length > 16) nickname = nickname.Substring(0, 16);
            Nickname = nickname;
            CharacterIndex = Mathf.Clamp(characterIndex, 0, GameDatabase.Instance.characters.Count - 1);
        }

        [Rpc(RpcSources.InputAuthority, RpcTargets.StateAuthority)]
        public void Rpc_SetCharacter(int characterIndex)
        {
            CharacterIndex = Mathf.Clamp(characterIndex, 0, GameDatabase.Instance.characters.Count - 1);
        }

        [Rpc(RpcSources.InputAuthority, RpcTargets.StateAuthority)]
        public void Rpc_SetReady(NetworkBool ready)
        {
            Ready = ready;
        }

        public void ResetForLobby()
        {
            if (!HasStateAuthority) return;
            Ready = false;
        }

        public void ResetRunStats()
        {
            if (!HasStateAuthority) return;
            Kills = 0;
            DamageDealt = 0;
        }
    }
}
