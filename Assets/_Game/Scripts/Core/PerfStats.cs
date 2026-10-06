using System.Diagnostics;

namespace MultiBash
{
    /// <summary>Cheap timing buckets for the telemetry log (dev only).</summary>
    public static class PerfStats
    {
        public static readonly Stopwatch EnemySim = new();
        public static readonly Stopwatch EnemyRender = new();
        public static readonly Stopwatch Weapons = new();
        public static readonly Stopwatch Fx = new();
        public static readonly Stopwatch Hud = new();
        public static int Frames;

        public static string Report()
        {
            float f = System.Math.Max(1, Frames);
            string s = $"msPerFrame enemySim={EnemySim.Elapsed.TotalMilliseconds / f:0.00} enemyRender={EnemyRender.Elapsed.TotalMilliseconds / f:0.00} weapons={Weapons.Elapsed.TotalMilliseconds / f:0.00} fx={Fx.Elapsed.TotalMilliseconds / f:0.00} hud={Hud.Elapsed.TotalMilliseconds / f:0.00}";
            EnemySim.Reset(); EnemyRender.Reset(); Weapons.Reset(); Fx.Reset(); Hud.Reset(); Frames = 0;
            return s;
        }
    }
}
