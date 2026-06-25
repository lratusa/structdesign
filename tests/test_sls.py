"""
正常使用极限状态测试（手算核对）。

裂缝: b=250,h=500,C30(ftk=2.01),As=1140,Mq=100kN·m,c=25,d=22,h0=460,HRB400(Es=2e5)
  Ate=62500; ρte=1140/62500=0.018240
  σsq=100e6/(0.87·460·1140)=219.2 N/mm²
  ψ=1.1-0.65·2.01/(0.018240·219.2)=0.7732
  deq=22/1.0=22
  ωmax=1.9·0.7732·(219.2/2e5)·(1.9·25+0.08·22/0.018240)
      =1.9·0.7732·0.0010960·143.99 = 0.232 mm  (<0.3 ✓)
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structdesign.codes import gb50010_sls as sls


def approx(a, b, tol=2e-2):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_crack_width():
    r = sls.crack_width(250, 500, 1140, 100, "C30", "HRB400",
                        d_bar=22, c=25, a_s=40)
    assert approx(r.rho_te, 0.018240, 1e-3), r.rho_te
    assert approx(r.sigma_sq, 219.2, 1e-2), r.sigma_sq
    assert approx(r.psi, 0.7732, 2e-2), r.psi
    assert approx(r.wmax, 0.232, 5e-2), r.wmax
    assert r.ok


def test_deflection_runs():
    r = sls.deflection(250, 500, 1140, 80, 6000, "C30", "HRB400", a_s=40)
    assert r.f > 0 and r.B > 0
    # 合理性：长期挠度应大于若干 mm 量级且有限
    assert 0 < r.f < 100


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS  {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
