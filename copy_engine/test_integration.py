"""快速测试脚本：验证媒体生成功能是否正常"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试所有必要的导入"""
    print("测试导入...")
    try:
        from app import create_app
        from app.services.media_generation_service import MediaGenerationService
        from app.routes.media import bp as media_bp
        print("✓ 所有导入成功")
        return True
    except Exception as e:
        print(f"✗ 导入失败: {e}")
        return False

def test_app_creation():
    """测试应用创建"""
    print("\n测试应用创建...")
    try:
        from app import create_app
        app = create_app()
        print("✓ 应用创建成功")
        
        # 检查扩展是否注册
        if 'media_service' in app.extensions:
            print("✓ 媒体服务已注册")
        else:
            print("✗ 媒体服务未注册")
            return False
        
        # 检查路由是否注册
        routes = [str(rule) for rule in app.url_map.iter_rules()]
        media_routes = [r for r in routes if '/media' in r]
        if media_routes:
            print(f"✓ 媒体路由已注册: {len(media_routes)} 个路由")
            for route in media_routes:
                print(f"  - {route}")
        else:
            print("✗ 媒体路由未注册")
            return False
        
        return True
    except Exception as e:
        print(f"✗ 应用创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ffmpeg():
    """测试 ffmpeg 是否可用"""
    print("\n测试 ffmpeg...")
    import subprocess
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✓ ffmpeg 可用: {version_line}")
            return True
        else:
            print("✗ ffmpeg 不可用")
            return False
    except FileNotFoundError:
        print("✗ ffmpeg 未安装或不在 PATH 中")
        print("  请安装 ffmpeg: https://www.gyan.dev/ffmpeg/builds/")
        return False
    except Exception as e:
        print(f"✗ ffmpeg 测试失败: {e}")
        return False

def test_dependencies():
    """测试 Python 依赖"""
    print("\n测试 Python 依赖...")
    dependencies = {
        'Pillow': 'PIL',
        'requests': 'requests',
        'openai': 'openai',
        'flask': 'flask',
    }
    
    all_ok = True
    for name, import_name in dependencies.items():
        try:
            __import__(import_name)
            print(f"✓ {name} 已安装")
        except ImportError:
            print(f"✗ {name} 未安装")
            all_ok = False
    
    return all_ok

def main():
    """运行所有测试"""
    print("=" * 60)
    print("媒体生成功能集成测试")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(("导入测试", test_imports()))
    results.append(("依赖测试", test_dependencies()))
    results.append(("ffmpeg 测试", test_ffmpeg()))
    results.append(("应用创建测试", test_app_creation()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ 所有测试通过！系统已准备就绪。")
        print("\n下一步:")
        print("1. 启动应用: python app.py")
        print("2. 访问: http://127.0.0.1:5000")
        print("3. 登录后点击导航栏的'媒体生成'")
    else:
        print("✗ 部分测试失败，请检查上述错误信息。")
        print("\n常见问题:")
        print("- 缺少依赖: pip install -r requirements.txt")
        print("- ffmpeg 未安装: 下载并添加到 PATH")
        print("- 导入错误: 检查文件路径和语法")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
