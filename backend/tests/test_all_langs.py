"""Quick smoke test — all 5 Piston runtimes."""
import asyncio
from services.piston_client import run_code

TESTS = [
    ("python",     'print("py ok")'),
    ("javascript", 'console.log("js ok")'),
    ("java",       'public class Main { public static void main(String[] a) { System.out.println("java ok"); } }'),
    ("cpp",        '#include<iostream>\nint main(){ std::cout<<"cpp ok"<<std::endl; }'),
    ("c",          '#include<stdio.h>\nint main(){ printf("c ok\\n"); }'),
]

async def main():
    all_pass = True
    for lang, code in TESTS:
        r = await run_code(code, lang)
        ok = r["exit_code"] == 0
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"{lang:12} exit={r['exit_code']}  stdout={repr(r['stdout'].strip())}  {status}")
        if not ok:
            print(f"             stderr={repr(r['stderr'][:120])}")
    print()
    print("All languages OK!" if all_pass else "SOME TESTS FAILED")

asyncio.run(main())
