// Skybox: vertical gradient + chunky pixelated clouds (Megabonk-like blue dusk sky).
Shader "MultiBash/PixelSky"
{
    Properties
    {
        _TopColor ("Top", Color) = (0.13, 0.42, 0.72, 1)
        _HorizonColor ("Horizon", Color) = (0.32, 0.62, 0.78, 1)
        _BottomColor ("Below Horizon", Color) = (0.18, 0.36, 0.45, 1)
        _CloudColor ("Clouds", Color) = (0.55, 0.75, 0.88, 1)
        _CloudScale ("Cloud Scale", Float) = 3.0
        _CloudCover ("Cloud Cover", Range(0, 1)) = 0.45
        _Pixel ("Pixel Size (lower = chunkier)", Float) = 90
        _Speed ("Cloud Speed", Float) = 0.004
        _StarDensity ("Stars (0 = none)", Range(0, 1)) = 0
        _MoonColor ("Moon", Color) = (1, 0.97, 0.85, 1)
        _MoonSize ("Moon Size (0 = none)", Range(0, 0.3)) = 0
        _MoonDir ("Moon Direction", Vector) = (0.3, 0.45, 0.85, 0)
        _AuroraA ("Aurora A", Color) = (0.3, 1, 0.65, 1)
        _AuroraB ("Aurora B", Color) = (0.6, 0.35, 1, 1)
        _Aurora ("Aurora Strength", Range(0, 2)) = 0
    }
    SubShader
    {
        Tags { "Queue"="Background" "RenderType"="Background" "PreviewType"="Skybox" }
        Cull Off ZWrite Off
        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            half4 _TopColor, _HorizonColor, _BottomColor, _CloudColor;
            float _CloudScale, _CloudCover, _Pixel, _Speed;
            float _StarDensity, _MoonSize, _Aurora;
            half4 _MoonColor, _AuroraA, _AuroraB;
            float4 _MoonDir;

            struct A { float4 pos : POSITION; };
            struct V { float4 pos : SV_POSITION; float3 dir : TEXCOORD0; };

            V vert (A v) { V o; o.pos = TransformObjectToHClip(v.pos.xyz); o.dir = v.pos.xyz; return o; }

            float hash(float2 p) { return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453); }
            float noise(float2 p)
            {
                float2 i = floor(p), f = frac(p);
                f = f * f * (3 - 2 * f);
                return lerp(lerp(hash(i), hash(i + float2(1, 0)), f.x), lerp(hash(i + float2(0, 1)), hash(i + float2(1, 1)), f.x), f.y);
            }
            float fbm(float2 p) { float s = 0, a = 0.5; for (int k = 0; k < 4; k++) { s += noise(p) * a; p *= 2.1; a *= 0.5; } return s; }

            half4 frag (V i) : SV_Target
            {
                float3 d = normalize(i.dir);
                float h = d.y;
                half3 col = h > 0 ? lerp(_HorizonColor.rgb, _TopColor.rgb, pow(saturate(h), 0.6)) : lerp(_HorizonColor.rgb, _BottomColor.rgb, saturate(-h * 4));
                // pixel-snapped direction for stars / aurora (chunky like the clouds)
                float3 pd = floor(d * _Pixel * 1.5) / (_Pixel * 1.5);
                if (_StarDensity > 0 && h > 0.05)
                {
                    float s = hash(pd.xz * 913.1 + pd.y * 37.7);
                    float tw = 0.6 + 0.4 * sin(_Time.y * 2.0 + s * 40.0);
                    col += step(1 - _StarDensity * 0.02, s) * tw * saturate(h * 3) * 0.9;
                }
                if (_Aurora > 0 && h > 0.03)
                {
                    // curtains: bands along a wavy line, rippling over time
                    float2 a = pd.xz / (h + 0.25);
                    float wave = sin(a.x * 1.7 + _Time.y * 0.25) * 0.6 + sin(a.x * 4.3 - _Time.y * 0.4) * 0.2;
                    float band = saturate(1 - abs(a.y - 0.8 - wave) * 1.6);
                    float rays = 0.55 + 0.45 * noise(float2(a.x * 9 + _Time.y * 0.6, 0));
                    float k = band * band * rays * saturate((h - 0.03) * 4) * saturate(1.2 - h);
                    k = floor(k * 6) / 6;
                    col += lerp(_AuroraA.rgb, _AuroraB.rgb, saturate(h * 1.8 + wave * 0.3)) * k * _Aurora;
                }
                if (_MoonSize > 0)
                {
                    float3 md = normalize(_MoonDir.xyz);
                    float m = dot(normalize(pd), md);
                    float disc = step(cos(_MoonSize), m);
                    float glow = pow(saturate((m - cos(_MoonSize * 3)) / (1 - cos(_MoonSize * 3))), 4) * 0.18;
                    float crater = step(0.72, noise(pd.xz * 160)) * 0.12;
                    col = lerp(col, _MoonColor.rgb * (1 - crater), disc) + _MoonColor.rgb * glow * (1 - disc);
                }
                if (h > 0.02)
                {
                    // project onto a cloud plane and quantize -> pixel clouds
                    float2 uv = d.xz / (h + 0.15) * _CloudScale;
                    uv = floor(uv * _Pixel / _CloudScale) / (_Pixel / _CloudScale);
                    uv += _Time.y * _Speed * float2(1, 0.3);
                    float c = fbm(uv * 0.35);
                    float m = step(1 - _CloudCover, c) * saturate((h - 0.02) * 6);
                    float m2 = step(1 - _CloudCover * 0.75, c);
                    col = lerp(col, _CloudColor.rgb, m * 0.65);
                    col = lerp(col, _CloudColor.rgb * 1.15, m2 * m * 0.4);
                }
                return half4(col, 1);
            }
            ENDHLSL
        }
    }
}
