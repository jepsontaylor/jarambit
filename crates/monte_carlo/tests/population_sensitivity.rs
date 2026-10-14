//! T03-09 and T03-10. Active lookup does not draw a medium.
use jarambit_monte_carlo::{
    active_cut_medium, env_temp_band, historical_medium, media_from_unit, population_shift, CheckedError, CutMedia,
};

#[test]
fn population_shift_rates_stay_constant_for_repetitions() {
    for k in [1u64, 2, u64::MAX / 10] {
        let s = population_shift(k).unwrap();
        assert_eq!(s.service.text(), "1/10");
        assert_eq!(s.discovery.text(), "1/2");
        assert_eq!(s.gap.text(), "2/5");
        assert_eq!(s.label, "assumed_model_population_discrepancy");
        assert_eq!(s.mc_error, 0);
        assert_ne!(s.service.text(), "3/10");
    }
    assert_eq!(population_shift(0), Err(CheckedError::InvalidConfig));
    assert_eq!(population_shift(u64::MAX / 10 + 1), Err(CheckedError::InvalidConfig));
    assert_eq!(population_shift(u64::MAX), Err(CheckedError::InvalidConfig));
}

#[test]
fn retired_media_profiles_and_active_lookup() {
    let expect = [
        ("wood", CutMedia::Wood, 100.0, 0.35, 0.35),
        ("cord", CutMedia::Cord, 70.0, 0.85, 0.55),
        ("hide", CutMedia::Hide, 45.0, 0.90, 0.50),
        ("muscle", CutMedia::Muscle, 90.0, 0.70, 0.55),
        ("bone", CutMedia::Bone, 160.0, 0.20, 0.25),
        ("gel", CutMedia::Gel, 60.0, 0.50, 0.30),
    ];
    for (name, media, work, lead, edge) in expect {
        assert_eq!(media.profile(), (work, lead, edge));
        assert_eq!(media.name(), name);
        let decoded = historical_medium(name).unwrap();
        assert_eq!((decoded.work, decoded.lead, decoded.edge, decoded.label), (work, lead, edge, "model_retired"));
    }
    assert!(historical_medium("deleted").is_none());
    assert_eq!(active_cut_medium().unwrap_err(), CheckedError::RetiredLookup);
    assert_eq!(media_from_unit(0.0), CutMedia::Wood);
    assert_eq!(media_from_unit(0.20), CutMedia::Cord);
    assert_eq!(media_from_unit(0.40), CutMedia::Hide);
    assert_eq!(media_from_unit(0.55), CutMedia::Muscle);
    assert_eq!(media_from_unit(0.75), CutMedia::Bone);
    assert_eq!(media_from_unit(0.85), CutMedia::Gel);
    assert_eq!(env_temp_band(0.0), Some(-10.0));
    assert_eq!(env_temp_band(0.125), Some(100.0));
    assert_eq!(env_temp_band(0.25), None);
}
