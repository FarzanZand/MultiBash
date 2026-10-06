// Animated pixel-art lava: two scrolling layers of a point-filtered lava texture, emissive (blooms), with fog.
Shader "MultiBash/PixelLava"
{
    Properties
    {
        _MainTex ("Lava Texture", 2D) = "white" {}
        _Tint ("Tint", Color) = (1, 1, 1, 1)
        _Glow ("Glow", Float) = 2.2
        _Flow ("Flow (xy layer1, zw unused)", Vector) = (0.02, 0.012, 0, 0)
        _Tile ("World Tile (m)", Float) = 6
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry" }
        Pass
        {
            Tags { "LightMode"="UniversalForward" }
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fog
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            CBUFFER_START(UnityPerMaterial)
                half4 _Tint;
                float _Glow;
                float4 _Flow;
                float _Tile;
                float4 _MainTex_ST;
            CBUFFER_END

            struct A { float4 pos : POSITION; };
            struct V { float4 pos : SV_POSITION; float3 ws : TEXCOORD0; half fog : TEXCOORD1; };

            V vert (A v)
            {
                V o;
                o.ws = TransformObjectToWorld(v.pos.xyz);
                o.pos = TransformWorldToHClip(o.ws);
                o.fog = ComputeFogFactor(o.pos.z);
                return o;
            }

            half4 frag (V i) : SV_Target
            {
                float2 uv = i.ws.xz / _Tile;
                half3 a = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uv + _Time.y * _Flow.xy).rgb;
                half3 b = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uv * 0.73 + float2(0.37, 0.11) - _Time.y * _Flow.yx * 0.8).rgb;
                half3 c = max(a, b * 0.9);
                // slow pulsing hot spots
                c *= 0.85 + 0.15 * sin(_Time.y * 1.5 + i.ws.x * 0.3 + i.ws.z * 0.2);
                c *= _Tint.rgb * _Glow;
                c = MixFog(c, i.fog);
                return half4(c, 1);
            }
            ENDHLSL
        }
    }
}
