import { render, screen } from "@testing-library/react";
import { useState } from "react";
import type { Shape, ShapeKind } from "../shapes";
import { drag } from "../test-utils";
import { ImageMarkup } from "./ImageMarkup";

function Harness({ tool = "box", single = false, readOnly = false, onChange = vi.fn() }: {
  tool?: ShapeKind;
  single?: boolean;
  readOnly?: boolean;
  onChange?: (s: Shape[]) => void;
}) {
  const [shapes, setShapes] = useState<Shape[]>([]);
  return (
    <ImageMarkup
      src="data:image/jpeg;base64,/9j/AAAA"
      alt="snapshot"
      shapes={shapes}
      tool={tool}
      single={single}
      readOnly={readOnly}
      onChange={(next) => {
        setShapes(next);
        onChange(next);
      }}
    />
  );
}

test("dragging draws a box in fractions of the image", () => {
  const onChange = vi.fn();
  render(<Harness onChange={onChange} />);
  drag([10, 10], [40, 50]);
  expect(onChange).toHaveBeenLastCalledWith([{ kind: "box", x1: 0.1, y1: 0.1, x2: 0.4, y2: 0.5 }]);
  expect(screen.getAllByTestId("markup-shape")).toHaveLength(1);
});

test("the line tool draws a line", () => {
  const onChange = vi.fn();
  render(<Harness tool="line" onChange={onChange} />);
  drag([50, 50], [90, 90]);
  expect(onChange).toHaveBeenLastCalledWith([{ kind: "line", x1: 0.5, y1: 0.5, x2: 0.9, y2: 0.9 }]);
});

test("shapes add up unless single", () => {
  const onChange = vi.fn();
  render(<Harness onChange={onChange} />);
  drag([10, 10], [40, 50]);
  drag([60, 60], [90, 90]);
  expect(onChange.mock.lastCall![0]).toHaveLength(2);
});

// Redraw replaces the box
test("with single, a new drag replaces the box", () => {
  const onChange = vi.fn();
  render(<Harness single onChange={onChange} />);
  drag([10, 10], [40, 50]);
  drag([60, 60], [90, 90]);
  expect(onChange).toHaveBeenLastCalledWith([{ kind: "box", x1: 0.6, y1: 0.6, x2: 0.9, y2: 0.9 }]);
  expect(screen.getAllByTestId("markup-shape")).toHaveLength(1);
});

// Tiny drag ignored
test("a tiny drag draws nothing", () => {
  const onChange = vi.fn();
  render(<Harness onChange={onChange} />);
  drag([50, 50], [51, 90]);
  expect(onChange).not.toHaveBeenCalled();
  expect(screen.queryAllByTestId("markup-shape")).toHaveLength(0);
});

test("read-only ignores drags", () => {
  const onChange = vi.fn();
  render(<Harness readOnly onChange={onChange} />);
  drag([10, 10], [40, 50]);
  expect(onChange).not.toHaveBeenCalled();
});

test("drags past the edge are clamped to the image", () => {
  const onChange = vi.fn();
  render(<Harness onChange={onChange} />);
  drag([80, 80], [130, 120]);
  expect(onChange).toHaveBeenLastCalledWith([{ kind: "box", x1: 0.8, y1: 0.8, x2: 1, y2: 1 }]);
});
