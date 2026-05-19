from pathlib import Path

from kreator.core.renderer import render_template_dir


def test_renders_j2_files(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "hello.txt.j2").write_text("Hello {{ name }}!")

    output = tmp_path / "output"
    render_template_dir(source, output, {"name": "world"})

    result = output / "hello.txt"
    assert result.exists()
    assert result.read_text() == "Hello world!"
    assert not (output / "hello.txt.j2").exists()


def test_copies_non_j2_files(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "static.txt").write_text("no templates here")

    output = tmp_path / "output"
    render_template_dir(source, output, {})

    result = output / "static.txt"
    assert result.exists()
    assert result.read_text() == "no templates here"


def test_creates_directories(tmp_path: Path):
    source = tmp_path / "source"
    nested = source / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "file.txt.j2").write_text("depth={{ name }}")

    output = tmp_path / "output"
    render_template_dir(source, output, {"name": "deep"})

    result = output / "a" / "b" / "file.txt"
    assert result.exists()
    assert result.read_text() == "depth=deep"


def test_renders_directory_names(tmp_path: Path):
    source = tmp_path / "source"
    templated_dir = source / "{{ project }}"
    templated_dir.mkdir(parents=True)
    (templated_dir / "config.txt").write_text("inside")

    output = tmp_path / "output"
    render_template_dir(source, output, {"project": "my-app"})

    result = output / "my-app" / "config.txt"
    assert result.exists()
    assert result.read_text() == "inside"


def test_mixed_j2_and_static(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "template.yaml.j2").write_text("name: {{ name }}")
    (source / "readme.md").write_text("static content")

    output = tmp_path / "output"
    render_template_dir(source, output, {"name": "test"})

    assert (output / "template.yaml").read_text() == "name: test"
    assert (output / "readme.md").read_text() == "static content"
