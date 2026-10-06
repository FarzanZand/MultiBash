using UnityEngine;

namespace MultiBash
{
    /// <summary>
    /// Code-driven animation for the low-poly models (no animation clips needed).
    /// Uses child parts named Body, Head, ArmL/ArmR (+ ForeArmL/ForeArmR), LegL/LegR (+ ShinL/ShinR).
    /// Missing parts are simply skipped; models without limbs (slimes) get squash &amp; stretch instead.
    ///
    /// Poses: idle breathing, run cycle with knee/elbow bends, torso twist and head bob, jump tuck,
    /// landing squash, slide, overhead melee swing, cast, hit recoil and downed.
    /// Put this on a wrapper object above the model (it rotates/scales its own transform).
    /// </summary>
    public class ProceduralRig : MonoBehaviour
    {
        [Header("Run cycle")]
        [Tooltip("Strides per meter traveled.")]
        public float stepFrequency = 1.3f;
        public float legSwing = 42f;
        public float kneeBend = 70f;
        public float armSwing = 38f;
        public float bobHeight = 0.07f;
        [Tooltip("Speed (m/s) that counts as a full run.")]
        public float runSpeed = 6f;
        [Tooltip("Squash & stretch for blob models like slimes.")]
        public bool blob;
        [Tooltip("Seconds for a melee swing / a cast gesture (heroes use slower, weightier gestures).")]
        public float attackTime = 0.42f, castTime = 0.35f;
        [Tooltip("Arms held slightly away from the body (degrees) so they don't clip through wide torsos.")]
        public float armSpread = 0f;

        Transform _body, _head, _armL, _armR, _foreL, _foreR, _legL, _legR, _shinL, _shinR, _wingL, _wingR;
        Quaternion _wingLRot, _wingRRot;
        Quaternion _bodyRot, _headRot, _armLRot, _armRRot, _foreLRot, _foreRRot, _legLRot, _legRRot, _shinLRot, _shinRRot;
        Vector3 _bodyPos, _scale;
        // rest rotation of each joint relative to this rig: lets character-space rotations drive joints whose local axes
        // differ (skinned bones from an armature) exactly like the old axis-aligned parts
        readonly System.Collections.Generic.Dictionary<Transform, Quaternion> _rel = new();

        float _phase, _speed, _vy, _run, _headLag;
        bool _air, _wasAir, _sliding;
        float _attackT = 1f, _castT = 1f, _hitT = 1f, _landT = 1f, _downed, _slide, _airBlend, _idleT;

        void Awake() => Rebind();

        void Reparent(string child, string parent)
        {
            var c = Find(child);
            var p = Find(parent);
            if (c != null && p != null && c.parent != p) c.SetParent(p, true);
        }

        /// <summary>Find the model's parts (call again after swapping/instantiating the model under this object).</summary>
        public void Rebind()
        {
            // sub-parts are exported flat; build the joint chain here (keeping world placement)
            Reparent("ForeArmL", "ArmL");
            Reparent("ForeArmR", "ArmR");
            Reparent("ShinL", "LegL");
            Reparent("ShinR", "LegR");
            Reparent("Head", "Body");

            _scale = transform.localScale;
            _body = Find("Body");
            _head = Find("Head");
            _armL = Find("ArmL");
            _armR = Find("ArmR");
            _foreL = Find("ForeArmL");
            _foreR = Find("ForeArmR");
            _legL = Find("LegL");
            _legR = Find("LegR");
            _shinL = Find("ShinL");
            _shinR = Find("ShinR");
            _wingL = Find("WingL");
            _wingR = Find("WingR");
            if (_wingL) _wingLRot = _wingL.localRotation;
            if (_wingR) _wingRRot = _wingR.localRotation;
            if (_body) { _bodyRot = _body.localRotation; _bodyPos = _body.localPosition; }
            if (_head) _headRot = _head.localRotation;
            if (_armL) _armLRot = _armL.localRotation;
            if (_armR) _armRRot = _armR.localRotation;
            if (_foreL) _foreLRot = _foreL.localRotation;
            if (_foreR) _foreRRot = _foreR.localRotation;
            if (_legL) _legLRot = _legL.localRotation;
            if (_legR) _legRRot = _legR.localRotation;
            if (_shinL) _shinLRot = _shinL.localRotation;
            if (_shinR) _shinRRot = _shinR.localRotation;
            _rel.Clear();
            foreach (var t in new[] { _body, _head, _armL, _armR, _foreL, _foreR, _legL, _legR, _shinL, _shinR, _wingL, _wingR })
                if (t != null) _rel[t] = Quaternion.Inverse(transform.rotation) * t.rotation;
            blob = blob || (_armL == null && _legL == null);
            if (_armL != null || _legL != null) blob = false;
            _phase = Random.value * 10f;
            _idleT = Random.value * 10f;
        }

        Transform Find(string n)
        {
            foreach (var t in GetComponentsInChildren<Transform>(true))
                if (t.name == n) return t;
            return null;
        }

        public Transform FindPart(string n) => Find(n);

        public void SetMotion(float speed, bool airborne) => SetMotion(speed, airborne, 0f);

        public void SetMotion(float speed, bool airborne, float verticalSpeed)
        {
            _speed = speed;
            _air = airborne;
            _vy = verticalSpeed;
        }

        public void SetSliding(bool sliding) => _sliding = sliding;
        // re-triggering while a gesture is still playing would snap the arm back: let it finish first
        public void Attack() { if (_attackT > 0.75f) _attackT = 0f; }
        public void Cast() { if (_castT > 0.7f && _attackT >= 1f) _castT = 0f; }
        public void Hit() => _hitT = 0f;
        public void SetDowned(bool downed) => _downed = downed ? 1f : 0f;

        static float Ease(float t) => t * t * (3f - 2f * t);

        /// <summary>The rig's up axis in the body's parent space (bones can have rotated parents).</summary>
        Vector3 BodyUp()
        {
            var p = _body.parent;
            return p == null ? Vector3.up : p.InverseTransformVector(transform.TransformVector(Vector3.up));
        }

        /// <summary>rest * rotation (euler, in character space) expressed in the joint's own frame.</summary>
        Quaternion Pose(Transform t, Quaternion rest, float x, float y, float z)
        {
            var e = Quaternion.Euler(x, y, z);
            if (!_rel.TryGetValue(t, out var rel)) return rest * e;
            return rest * (Quaternion.Inverse(rel) * e * rel);
        }

        void LateUpdate()
        {
            float dt = Time.deltaTime;
            _idleT += dt;
            _attackT += dt / Mathf.Max(0.05f, attackTime);
            _castT += dt / Mathf.Max(0.05f, castTime);
            _hitT += dt / 0.18f;
            if (_wasAir && !_air) _landT = 0f;
            _wasAir = _air;
            _landT += dt / 0.2f;

            if (_wingL != null || _wingR != null)
            {
                // flyers: fast wing flaps + body bob
                float flap = Mathf.Sin(Time.time * 22f + _phase) * 55f;
                if (_wingL) _wingL.localRotation = Pose(_wingL, _wingLRot, 0, 0, flap);
                if (_wingR) _wingR.localRotation = Pose(_wingR, _wingRRot, 0, 0, -flap);
                if (_body) _body.localPosition = _bodyPos + BodyUp() * Mathf.Sin(Time.time * 22f + _phase) * 0.05f;
                float sqh = 1f - (1f - Mathf.Clamp01(_hitT)) * 0.2f;
                transform.localScale = _scale * sqh;
                return;
            }

            if (blob)
            {
                float stretch = _air ? 0.18f : 0f;
                float squash = (1f - Mathf.Clamp01(_landT)) * 0.3f + (1f - Mathf.Clamp01(_hitT)) * 0.15f;
                float wobble = Mathf.Sin(Time.time * 6f + _phase) * 0.04f;
                float sy = 1f + stretch - squash + wobble;
                float sxz = 1f / Mathf.Sqrt(Mathf.Max(0.3f, sy));
                transform.localScale = new Vector3(_scale.x * sxz, _scale.y * sy, _scale.z * sxz);
                return;
            }

            // smoothed blends
            _run = Mathf.MoveTowards(_run, _air ? _run : Mathf.Clamp01(_speed / runSpeed), dt * 6f);
            _airBlend = Mathf.MoveTowards(_airBlend, _air && !_sliding ? 1f : 0f, dt * 8f);
            _slide = Mathf.MoveTowards(_slide, _sliding ? 1f : 0f, dt * 12f);
            if (!_air) _phase += _speed * stepFrequency * dt * Mathf.PI;

            float s = Mathf.Sin(_phase);
            float run = _run * (1f - _airBlend) * (1f - _slide);
            float idle = 1f - _run;
            float breathe = Mathf.Sin(_idleT * 2.2f);

            // ---- legs: swing from the hip, knee bends on the back-swing
            float kneeL = Mathf.Max(0f, Mathf.Sin(_phase + Mathf.PI * 0.5f)) * kneeBend * run;
            float kneeR = Mathf.Max(0f, Mathf.Sin(_phase - Mathf.PI * 0.5f)) * kneeBend * run;
            float legL = s * legSwing * run, legR = -s * legSwing * run;
            // jump tuck: thighs forward, knees bent (more on the way up)
            float tuck = _airBlend * (_vy > 0 ? 1f : 0.6f);
            legL += -45f * tuck; legR += -25f * tuck;
            kneeL += 75f * tuck; kneeR += 55f * tuck;
            // slide: legs out front, back knee bent
            legL += -70f * _slide; legR += -20f * _slide;
            kneeL += 5f * _slide; kneeR += 80f * _slide;
            // landing: crouch
            float land = (1f - Mathf.Clamp01(_landT)) * (1f - _slide);
            legL += -20f * land; legR += -20f * land;
            kneeL += 40f * land; kneeR += 40f * land;
            if (_legL) _legL.localRotation = Pose(_legL, _legLRot, legL, 0, 0);
            if (_legR) _legR.localRotation = Pose(_legR, _legRRot, legR, 0, 0);
            if (_shinL) _shinL.localRotation = Pose(_shinL, _shinLRot, kneeL, 0, 0);
            if (_shinR) _shinR.localRotation = Pose(_shinR, _shinRRot, kneeR, 0, 0);

            // ---- arms: counter-swing with bent elbows; raised in the air; back while sliding
            float armL = -s * armSwing * run + breathe * 2f * idle - 55f * _airBlend + 35f * _slide;
            float armR = s * armSwing * run - breathe * 2f * idle - 70f * _airBlend + 30f * _slide;
            float elbowL = -(15f + 30f * run + 30f * _airBlend);
            float elbowR = -(15f + 30f * run + 30f * _airBlend);
            float armRSide = 0f, bodyTwistExtra = 0f;

            if (_attackT < 1f)
            {
                // overhead swing: wind up over the head, then slash down across
                float t = _attackT;
                float raise = t < 0.3f ? Ease(t / 0.3f) : 1f - Ease(Mathf.Clamp01((t - 0.3f) / 0.35f));
                float strike = t < 0.3f ? 0f : Ease(Mathf.Clamp01((t - 0.3f) / 0.25f));
                float settle = t > 0.65f ? Ease((t - 0.65f) / 0.35f) : 0f;
                armR = Mathf.Lerp(armR, -165f * raise + 30f * strike * (1f - settle), 1f - settle);
                elbowR = Mathf.Lerp(elbowR, -20f * raise, 1f - settle);
                armRSide = -25f * strike * (1f - settle);
                bodyTwistExtra = (20f * raise - 30f * strike) * (1f - settle);
            }
            else if (_castT < 1f)
            {
                // cast: thrust the weapon arm forward
                float k = Mathf.Sin(Mathf.Clamp01(_castT) * Mathf.PI);
                armR = Mathf.Lerp(armR, -95f, k);
                elbowR = Mathf.Lerp(elbowR, -5f, k);
                bodyTwistExtra = -10f * k;
            }

            float spread = armSpread + 4f * run;
            if (_armL) _armL.localRotation = Pose(_armL, _armLRot, armL, 0, spread);
            if (_armR) _armR.localRotation = Pose(_armR, _armRRot, armR, 0, armRSide - spread);
            if (_foreL) _foreL.localRotation = Pose(_foreL, _foreLRot, elbowL, 0, 0);
            if (_foreR) _foreR.localRotation = Pose(_foreR, _foreRRot, elbowR, 0, 0);

            // ---- body: bob, forward lean, twist with the stride, recoil, breathing
            if (_body)
            {
                float bob = Mathf.Abs(Mathf.Cos(_phase)) * bobHeight * run;
                float crouch = -0.12f * land - 0.28f * _slide;
                float recoil = (1f - Mathf.Clamp01(_hitT)) * 14f;
                float lean = 10f * run - 8f * _slide;
                float twist = s * 9f * run + bodyTwistExtra;
                float roll = Mathf.Cos(_phase) * 3.5f * run + Mathf.Sin(_idleT * 0.9f) * 1.2f * idle;   // hip sway / idle shift
                _body.localPosition = _bodyPos + BodyUp() * (bob + crouch + breathe * 0.006f * idle);
                _body.localRotation = Pose(_body, _bodyRot, lean - recoil + 6f * _airBlend, twist, roll);
                _headLag = Mathf.Lerp(_headLag, twist + roll, 1f - Mathf.Exp(-6f * dt));
            }
            if (_head)
            {
                float nod = Mathf.Sin(_phase * 2f) * 3f * run + breathe * 1.5f * idle;
                // the head lags behind the torso and stays level: a little follow-through instead of a rigid stack
                float look = -Mathf.Sin(_phase) * 6f * run - bodyTwistExtra * 0.4f - _headLag * 0.5f;
                _head.localRotation = Pose(_head, _headRot, nod - 4f * run, look, -_headLag * 0.3f);
            }

            // ---- whole model: lie down when downed, lean back while sliding, squash on landing
            var target = Quaternion.Euler(-80f * _downed - 25f * _slide, 0, 0);
            transform.localRotation = Quaternion.Slerp(transform.localRotation, target, 10f * dt);
            float sq = 1f - land * 0.06f;
            transform.localScale = new Vector3(_scale.x * (2f - sq), _scale.y * sq, _scale.z * (2f - sq));
        }
    }
}
