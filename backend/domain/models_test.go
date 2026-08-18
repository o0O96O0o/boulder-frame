package domain

import (
	"testing"

	"github.com/google/uuid"
)

func TestNewJobConfigValidatesContract(t *testing.T) {
	cases := []struct {
		name      string
		selection TargetSelection
		output    OutputSettings
		wantErr   bool
	}{
		{"valid", TargetSelection{FrameTimeMS: 20, NormalizedX: .5, NormalizedY: .2}, OutputSettings{"16:9", "balanced"}, false},
		{"negative time", TargetSelection{FrameTimeMS: -1, NormalizedX: .5, NormalizedY: .2}, OutputSettings{"16:9", "balanced"}, true},
		{"bad coordinate", TargetSelection{NormalizedX: 1.1, NormalizedY: .2}, OutputSettings{"16:9", "balanced"}, true},
		{"bad ratio", TargetSelection{NormalizedX: .5, NormalizedY: .2}, OutputSettings{"1:1", "balanced"}, true},
		{"bad profile", TargetSelection{NormalizedX: .5, NormalizedY: .2}, OutputSettings{"16:9", "wide"}, true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := NewJobConfig(uuid.New(), tc.selection, tc.output, "pipeline", "model")
			if (err != nil) != tc.wantErr {
				t.Fatalf("error = %v, wantErr %v", err, tc.wantErr)
			}
		})
	}
}

func TestJobConfigHashIsStableAndChangesWithConfiguration(t *testing.T) {
	c, err := NewJobConfig(uuid.New(), TargetSelection{NormalizedX: .5, NormalizedY: .5}, OutputSettings{"16:9", "balanced"}, "p1", "m1")
	if err != nil {
		t.Fatal(err)
	}
	a, _ := c.Hash()
	b, _ := c.Hash()
	if a != b {
		t.Fatal("same configuration produced different hashes")
	}
	c.Output.Profile = "safe"
	d, _ := c.Hash()
	if a == d {
		t.Fatal("different configuration produced same hash")
	}
}
